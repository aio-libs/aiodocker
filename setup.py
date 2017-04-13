#!/usr/bin/env python

from setuptools import setup

version = "0.7b1"
long_description = "Docker API client for asyncio"

setup(
    name="aiodocker",
    version=version,
    author="Paul Tagliamonte",
    author_email="paultag@debian.org",
    long_description=long_description,
    description="Provides coroutine-based API wrapper for Docker daemons",
    license="Expat",
    url="",
    platforms=['any'],
    packages=[
        'aiodocker',
    ],
    python_requires='>=3.6',
    install_requires=[
        'aiohttp>=2.0',
        'yarl>=0.10',
    ],
    extras_require={
        'test': ['pytest', 'pytest-asyncio'],
    }
)
