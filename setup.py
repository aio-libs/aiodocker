#!/usr/bin/env python

from setuptools import setup

version = "0.6"
long_description = "AsyncIO Docker bindings"

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
        'aiohttp>=1.1',
        'async_timeout',
    ],
)
