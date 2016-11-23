# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""Celery integration with Zope 3.
"""

from setuptools import setup, find_packages
import glob
import os.path


def project_path(*names):
    return os.path.join(os.path.dirname(__file__), *names)


setup(
    name='z3c.celery',
    version='0.1.dev0',

    install_requires=[
        'setuptools',
    ],

    extras_require={
        'test': [
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
License :: OSI Approved
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 2 :: Only
Programming Language :: Python :: Implementation :: CPython
"""[:-1].split('\n'),
    description=__doc__.strip(),
    long_description='\n\n'.join(open(project_path(name)).read() for name in (
        'README.rst',
        'HACKING.rst',
        'CHANGES.rst',
    )),

    namespace_packages=['z3c'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('',
                 glob.glob(project_path('*.txt')),
                 glob.glob(project_path('*.rst')))],
    zip_safe=False,
)
