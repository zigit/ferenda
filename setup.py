#!/usr/bin/env python
from setuptools import setup, find_packages
import os
import sys

if os.path.exists("README.rst"):
    with open("README.rst") as fp:
        longdesc = fp.read()
else:
    longdesc = ""

install_requires = ['beautifulsoup4 >= 4.3.0',
                    'jsmin >= 2.0.2',
                    'cssmin >= 0.2.0',
                    'lxml >= 3.2.0',
                    'rdflib >= 4.0.1',
                    'html5lib >= 1.0b1',
                    'rdfextras >= 0.4',
                    'rdflib-jsonld >= 0.2',
                    'requests >= 1.2.0',
                    'Whoosh >= 2.4.1',
                    'future >= 0.15.0',
                    'docutils >= 0.11',
                    'layeredconfig >= 0.2.2',
                    'responses >= 0.3.0',
                    'SimpleParse >= 2.2.0',
                    'cached_property >= 1.3.0',
                    'langdetect >= 1.0.0',
                    # 'patchit >= 1.2',   # not released yet, using vendorized copy
]

if sys.version_info < (3,0,0):
    install_requires.append("configparser")
    
if sys.version_info < (2,7,0):
    install_requires.append('ordereddict >= 1.1')
    install_requires.append("importlib")

if sys.version_info >= (2,7,0):
    # grako won't even install on py26
    install_requires.append('grako >= 3.4.0')

tests_require = ['psutil']

if sys.version_info < (3,3,0):
    tests_require.append('mock >= 1.0.0')
if sys.version_info < (2,7,0):
    tests_require.append('unittest2 >= 0.5.1')

# we can't just import ferenda to get at ferenda.__version__ since it
# might have unmet dependencies at this point. Exctract it directly
# from the file (code from rdflib:s setup.py)
def find_version(filename):
    import re
    _version_re = re.compile(r'__version__ = "(.*)"')
    for line in open(filename):
        version_match = _version_re.match(line)
        if version_match:
            return version_match.group(1)

setup(name='ferenda',
      version=find_version('ferenda/__init__.py'),
      description='Transform unstructured document collections to structured Linked Data',
      long_description=longdesc,
      author='Staffan Malmgren',
      author_email='staffan.malmgren@gmail.com',
      url='https://github.com/staffanm/ferenda/',
      license='BSD',
      keywords='rdf linkeddata parsing', 
      install_requires=install_requires,
      tests_require=tests_require,
      entry_points = {
        'console_scripts':['ferenda-setup = ferenda.manager:runsetup']
        },
      packages=find_packages(exclude=('test', 'docs')),
      # package_dir = {'ferenda':'ferenda'},
      # package_data = {'ferenda':['res/css/*.css', 'res/js/*.js', 'res/xsl/*.xsl']},
      include_package_data = True,
      zip_safe = False,
      classifiers=[ 
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
          'Topic :: Text Processing',
          'Topic :: Text Processing :: Indexing',
          'Topic :: Text Processing :: Markup :: XML'
          ]
      )
