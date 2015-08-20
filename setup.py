#!/usr/bin/env python

import codecs
import os
import re
from setuptools import setup

with codecs.open(os.path.join(os.path.abspath(os.path.dirname(
        __file__)), 'aiodocker', '__init__.py'), 'r', 'latin1') as fp:
    try:
        version = re.findall(r'^__version__ = "([^"]+)"$', fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')

long_description = "AsyncIO Docker bindings"

setup(
    name="aiodocker",
    version=version,
    packages=['aiodocker', ],  # This is empty without the line below
    author="Paul Tagliamonte",
    author_email="paultag@debian.org",
    long_description=long_description,
    description='does some stuff with things & stuff',
    license="Expat",
    url="",
    platforms=['any']
)
