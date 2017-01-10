from setuptools import setup, find_packages

setup(
    name='aiodocker',
    version='0.6.1',
    author='Paul Tagliamonte, Konstantin Itskov',
    author_email='paultag@debian.org, konstantin.itskov@findmine.com',
    long_description='AsyncIO Docker bindings',
    description='does some stuff with things & stuff',
    license='MIT',
    platforms=['any'],
    install_requires=[
        'aiohttp==1.2.0',
        'ujson==1.35'
    ],
    packages=find_packages()
)
