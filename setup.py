#!/usr/bin/env python

from setuptools import setup

version = "0.6"
long_description = "AsyncIO Docker bindings"

setup(
    name="aiodocker",
    version=version,
    packages=['aiodocker',],  # This is empty without the line below
    author="Paul Tagliamonte",
    author_email="paultag@debian.org",
    long_description=long_description,
    description='does some stuff with things & stuff',
    license="Expat",
    url="",
    platforms=['any']
)
