from setuptools import setup, find_packages

from pip.req import parse_requirements


version = '0.0.1'


setup(name='helga-cmg-fes',
      version=version,
      description=('CMG-only FE assignment management'),
      classifiers=[
          'Development Status :: 4 - Beta',
          'Topic :: Communications :: Chat :: Internet Relay Chat',
          'Framework :: Twisted',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
      keywords='helga FEs CMG',
      author='Shaun Duncan',
      author_email='shaun.duncan@gmail.com',
      url='https://github.com/shaunduncan/helga-cmg-fes',
      license='MIT',
      packages=find_packages(),
      py_modules=['helga_cmg_fes'],
      install_requires=[
          str(req.req) for req in parse_requirements('requirements.txt')
      ],
      entry_points = dict(
          helga_plugins=[
              'fes = helga_cmg_fes:fes',
          ],
      ),
)
