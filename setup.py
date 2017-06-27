#!/usr/bin/env python

from setuptools import setup

version = "0.7.1"

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    long_description = ""


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
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development',
        'Framework :: AsyncIO',
    ],
    url="https://github.com/aio-libs/aiodocker",
    platforms=['any'],
    packages=[
        'aiodocker',
    ],
    python_requires='>=3.6',
    install_requires=[
        'aiohttp~=2.2.0',
        'yarl>=0.10',
    ],
    extras_require={
        'test': ['pytest', 'pytest-asyncio', 'flake8'],
    }
)
