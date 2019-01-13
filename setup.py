#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('CHANGELOG.md') as history_file:
    history = history_file.read()

requirements = ['requests',
                'requests_ratelimit_adapter',
                'appdirs',
                'pony']

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest', ]

setup(
    author="Max Dymond",
    author_email='cmeister2@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Scryfall Cache is a library which minimizes the number of requests made to the Scryfall API.",
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',
    include_package_data=True,
    keywords='scryfall_cache',
    name='scryfall_cache',
    packages=find_packages(include=['scryfall_cache']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/cmeister2/scryfall_cache',
    version='0.2.1',
    zip_safe=False,
)
