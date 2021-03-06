#!/usr/bin/env python
from setuptools import setup

setup(
    name='sigtools',
    version='1.1a3',
    description="Utilities for working with 3.3's inspect.Signature objects.",
    license='MIT',
    author='Yann Kaiser',
    author_email='kaiser.yann@gmail.com',
    url='http://sigtools.readthedocs.org/',
    packages=['sigtools', 'sigtools.tests'],
    tests_require=[
        'repeated_test',
        'sphinx',
        'mock',
        'coverage',
        'unittest2'
        ],
    install_requires=['six'],
    extras_require={
        ':python_version in "2.6  2.7  3.2"': ['funcsigs>=0.4'],
        ':python_version in "2.6"': ['ordereddict'],
    },
    test_suite='unittest2.collector',
    keywords='introspection signature',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
