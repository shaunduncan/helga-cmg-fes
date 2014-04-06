import re

from datetime import datetime
from urlparse import urlparse, urlunparse

import requests

from BeautifulSoup import BeautifulSoup
from requests.auth import HTTPBasicAuth
from twisted.internet import reactor

from helga import settings
from helga.plugins import command, ResponseNotReady


FE_NAME_PAT = re.compile(r'FE[0-9]+')

# The row in confluence looks like: | <fe> | <owner> | <ticket> | <date> | <notes> |
FE_WIKI_ROW = re.compile(r'\|.?\[(FE[0-9]+)\|.*?\].?\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|')

# These are confluence links to JIRA tickets
JIRA_TICKET_PAT = re.compile(r'\{jstat:t=(.*?)\}')

AUTH = HTTPBasicAuth(username=settings.FES_CONFLUENCE_USER,
                     password=settings.FES_CONFLUENCE_PASS)


def _release(client, channel, name, nick):
    session = requests.Session()
    session.auth = AUTH

    json_data = session.get(settings.FES_CONFLUENCE_JSON_URL).json()

    find_pat = r'\|.?\[{name}\|(.*?)\].?\|.*?\|.*?\|.*?\|.*?\|'
    replace_pat = r'| [{name}|\1] | | {{jstat:t=}} | | |'

    # Generate new content
    new_content = re.sub(find_pat.format(name=name),
                         replace_pat.format(name=name),
                         json_data['body'])

    # Get the edit page contents
    soup = BeautifulSoup(session.get(settings.FES_CONFLUENCE_EDIT_URL).content)
    form = soup.find('form', {'id': 'editpageform'})

    # This is a pain. We have to get all of the form data into a dict
    params = dict(
        (f['name'], f.get('value', ''))
        for f in form.findAll('input')
        if f.get('name', '') and f['name'] != 'cancel'
    )

    # textareas
    params.update(dict(
        (f['name'], getattr(f, 'text', ''))
        for f in form.findAll('textarea')
        if f.get('name', '')
    ))

    # Update with new content
    params['content'] = new_content

    # Create the post url
    parsed = urlparse(settings.FES_CONFLUENCE_EDIT_URL)
    path = '/'.join([parsed.path.rpartition('/')[0], form['action']])
    action_url = urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))

    resp = session.post(action_url, data=params, auth=AUTH)

    if resp.status_code != 200:
        client.msg(channel, 'I was unable to release {fe} for you {nick}'.format(fe=name, nick=nick))

    else:
        client.msg(channel, '{fe} has been released, {nick}'.format(fe=name, nick=nick))


def _reserve(client, channel, name, owner, ticket='', notes=''):
    session = requests.Session()
    session.auth = AUTH

    json_data = session.get(settings.FES_CONFLUENCE_JSON_URL).json()

    find_pat = r'\|.?\[{name}\|(.*?)\].?\|.*?\|.*?\|.*?\|.*?\|'
    replace_pat = r'| [{name}|\1] | {owner} | {{jstat:t={ticket}}} | {now} | {notes} (reserved by helga) |'

    # Generate new content
    new_content = re.sub(find_pat.format(name=name),
                         replace_pat.format(name=name,
                                            owner=owner,
                                            ticket=ticket,
                                            now=datetime.now().strftime('%Y-%m-%d'),
                                            notes=notes),
                         json_data['body'])

    # Get the edit page contents
    soup = BeautifulSoup(session.get(settings.FES_CONFLUENCE_EDIT_URL).content)
    form = soup.find('form', {'id': 'editpageform'})

    # This is a pain. We have to get all of the form data into a dict
    params = dict(
        (f['name'], f.get('value', ''))
        for f in form.findAll('input')
        if f.get('name', '') and f['name'] != 'cancel'
    )

    # textareas
    params.update(dict(
        (f['name'], getattr(f, 'text', ''))
        for f in form.findAll('textarea')
        if f.get('name', '')
    ))

    # Update with new content
    params['content'] = new_content

    # Create the post url
    parsed = urlparse(settings.FES_CONFLUENCE_EDIT_URL)
    path = '/'.join([parsed.path.rpartition('/')[0], form['action']])
    action_url = urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))

    resp = session.post(action_url, data=params, auth=AUTH)

    if resp.status_code != 200:
        client.msg(channel, 'I was unable to reserve {fe} for you {nick}'.format(fe=name, nick=owner))

    else:
        client.msg(channel, '{fe} has been reserved, {nick}'.format(fe=name, nick=owner))


def _list(client, channel, available=False, fe_num=None):
    session = requests.Session()
    session.auth = AUTH
    data = session.get(settings.FES_CONFLUENCE_JSON_URL).json()

    fes = {}
    normalize = lambda s: s.strip(' \\').replace('&nbsp;', '')

    for match in FE_WIKI_ROW.findall(data['body']):
        fe, owner, tickets, reserved_on, notes = map(normalize, match)
        num = int(fe.replace('FE', ''))

        if available and owner:
            continue

        # Parse jira tickets
        ticket_nums = JIRA_TICKET_PAT.findall(tickets)

        # Fix notes
        notes = JIRA_TICKET_PAT.sub(r'\1', notes)

        fes[num] = {
            'owner': owner,
            'tickets': ', '.join(ticket_nums),
            'date': reserved_on,
            'notes': notes,
        }

    if available:
        fe_nums = map(lambda n: 'FE%d' % n, sorted(fes.keys()))
        client.msg(channel, 'Currently Available FEs: %s' % ', '.join(fe_nums))
    else:
        taken_format = 'FE{n}: reserved by {owner} on {date} for {tickets}. NOTES: {notes}'
        avail_format = 'FE{n}: available'

        # Are we only looking for one?
        if fe_num is not None:
            fes = {fe_num: fes[fe_num]}

        # Now print them
        for n in sorted(fes.keys()):
            fmt = taken_format if fes[n]['owner'] else avail_format
            msg = fmt.format(n=n, **fes[n]).strip()

            # Don't include notes if there aren't any
            if msg.endswith('NOTES:'):
                msg = msg.replace('NOTES:', '').strip()

            client.msg(channel, msg)


@command('fe', aliases=['fes'],
         help="Check FE assignments or reserve one. Usage: "
              "helga (fe|fes) [available|[fe]<num>|(reserve|release) fe<num> [<jira-ticket>] [NOTES]]")
def fes(client, channel, nick, message, cmd, args):
    try:
        subcmd = args.pop(0)
    except IndexError:
        reactor.callLater(0, _list, client, channel, available=False)
        raise ResponseNotReady

    if subcmd == 'available':
        reactor.callLater(0, _list, client, channel, available=True)
        raise ResponseNotReady

    # Possibly show single details
    if FE_NAME_PAT.match(subcmd.upper()) or subcmd.isdigit():
        num = int(subcmd.upper().replace('FE', ''))
        reactor.callLater(0, _list, client, channel, fe_num=num)

    if subcmd in ('reserve', 'release'):
        try:
            fe_name = args.pop(0).upper()
        except IndexError:
            return 'You must tell me what FE you want to {cmd}, {nick}'.format(cmd=subcmd, nick=nick)

        if not FE_NAME_PAT.match(fe_name):
            return '{fe} is not a valid FE name, {nick}'.format(fe=fe_name, nick=nick)

        try:
            jira_ticket = args.pop(0).upper()
        except IndexError:
            jira_ticket = ''

        notes = ' '.join(args)

        if subcmd == 'reserve':
            reactor.callLater(0, _reserve, client, channel, fe_name, nick, jira_ticket, notes)
        else:
            reactor.callLater(0, _release, client, channel, fe_name, nick)

        raise ResponseNotReady
