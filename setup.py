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


setup(
    name="aiodocker",
    version=version,
    author="Paul Tagliamonte",
    author_email="paultag@debian.org",
    long_description=long_description,
    description="Docker API client for asyncio",
    license="Expat",
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
    install_requires=[
        'setuptools==36.2.0'
        'aiohttp==2.2.3',
        'yarl>=0.10',
    ],
    extras_require={
        'test': ['pytest', 'pytest-asyncio', 'flake8'],
    }
)
