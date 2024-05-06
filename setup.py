#!/usr/bin/env python

import re
from pathlib import Path

from setuptools import setup


with (Path(__file__).parent / "aiodocker" / "__init__.py").open() as fp:
    try:
        version = re.findall(r'^__version__ = "([^"]+)"\r?$', fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError("Unable to determine version.")


long_description = open("README.rst").read()


requirements = [
    "aiohttp>=3.8",
    "async-timeout>=4.0.3",
    "typing_extensions>=4.0",
    "yarl>=1.7.2",
]


setup(
    name="aiodocker",
    version=version,
    author="Paul Tagliamonte",
    author_email="paultag@debian.org",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    description="Docker API client for asyncio",
    license="Apache 2",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development",
        "Framework :: AsyncIO",
    ],
    url="https://github.com/aio-libs/aiodocker",
    platforms=["any"],
    packages=["aiodocker"],
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=requirements,
)
