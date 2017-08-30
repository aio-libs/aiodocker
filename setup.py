#!/usr/bin/env python

import re
from pathlib import Path

from setuptools import setup

with (Path(__file__).parent / 'aiodocker' / '__init__.py').open() as fp:
    try:
        version = re.findall(r"^__version__ = '([^']+)'\r?$",
                             fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')


long_description = open('README.rst').read() + open('CHANGES.rst').read()


with open('./requirements/base.txt') as test_reqs_txt:
    requirements = list(iter(test_reqs_txt))


with open('./requirements/test.txt') as test_reqs_txt:
    test_requirements = list(iter(test_reqs_txt))


setup(
    name="aiodocker",
    version=version,
    author="Paul Tagliamonte",
    author_email="paultag@debian.org",
    long_description=long_description,
    description="Docker API client for asyncio",
    license="Apache 2",
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Framework :: AsyncIO',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development',
        'Framework :: AsyncIO',
    ],
    url="https://github.com/aio-libs/aiodocker",
    platforms=['any'],
    packages=[
        'aiodocker',
    ],
    python_requires='>=3.5',
    install_requires=requirements,
    tests_require=test_requirements,
    test_suite="tests",
)
