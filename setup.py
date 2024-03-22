# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""Integration of Celery 4 with Zope 3.
"""

from setuptools import setup, find_packages

setup(
    name='z3c.celery',
    version='1.7.0',

    install_requires=[
        'celery >= 4.0.2',
        'setuptools',
        'transaction',
        'ZODB',
        'zope.app.appsetup',
        'zope.app.publication',
        'zope.app.wsgi',
        'zope.authentication',
        'zope.component',
        'zope.exceptions',
        'zope.interface',
        'zope.publisher',
        'zope.security',
        'zope.principalregistry',
    ],

    extras_require={
        'test': [
            'pytest',
            'pytest-celery',
            'gocept.pytestlayer',
            'plone.testing',
            'redis',
            'tblib',
            'zope.traversing',
        ],
        'layer': [  # use this extra when using the EndToEndLayer
            'plone.testing',
        ],

    },

    entry_points={
        'console_scripts': [
            # 'binary-name = z3c.celery.module:function'
        ],
    },

    author='gocept, Zeit Online',
    author_email='zon-backend@zeit.de',
    license='BSD',
    url='https://github.com/ZeitOnline/z3c.celery',
    keywords='celery Zope transaction',
    classifiers="""\
Development Status :: 3 - Alpha
Framework :: Zope3
Intended Audience :: Developers
License :: OSI Approved
License :: OSI Approved :: BSD License
Natural Language :: English
Operating System :: OS Independent
Programming Language :: Python
Programming Language :: Python :: 3.7
Programming Language :: Python :: Implementation :: CPython
Topic :: Database
Topic :: Software Development
Topic :: Software Development :: Testing
"""[:-1].split('\n'),
    description=__doc__.strip(),
    long_description='\n\n'.join(open(name).read() for name in (
        'README.rst',
        'CHANGES.rst',
    )),
    namespace_packages=['z3c'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
)
