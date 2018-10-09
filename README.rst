==============================
AsyncIO bindings for docker.io
==============================

.. image:: https://badge.fury.io/py/aiodocker.svg
   :target: https://badge.fury.io/py/aiodocker
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/aiodocker.svg
   :target: https://pypi.org/project/aiodocker/
   :alt: Python Versions

.. image:: https://travis-ci.com/aio-libs/aiodocker.svg?branch=master
   :target: https://travis-ci.com/aio-libs/aiodocker
   :alt: Build Status

.. image:: https://codecov.io/gh/aio-libs/aiodocker/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/aio-libs/aiodocker
   :alt: Code Coverage

.. image:: https://badges.gitter.im/Join%20Chat.svg
    :target: https://gitter.im/aio-libs/Lobby
    :alt: Chat on Gitter

A simple Docker HTTP API wrapper written with asyncio and aiohttp.


Installation
============

.. code-block:: sh

   pip install aiodocker

Documentation
=============

http://aiodocker.readthedocs.io


Examples
========

.. code-block:: python

   import asyncio
   import aiodocker

   async def list_things():
       docker = aiodocker.Docker()
       print('== Images ==')
       for image in (await docker.images.list()):
           tags = image['RepoTags'][0] if image['RepoTags'] else ''
           print(image['Id'], tags)
       print('== Containers ==')
       for container in (await docker.containers.list()):
           print(f" {container._id}")
       await docker.close()

   async def run_container():
       docker = aiodocker.Docker()
       print('== Running a hello-world container ==')
       container = await docker.containers.create_or_replace(
           config={
               'Cmd': ['/bin/ash', '-c', 'echo "hello world"'],
               'Image': 'alpine:latest',
           },
           name='testing',
       )
       await container.start()
       logs = await container.log(stdout=True)
       print(''.join(logs))
       await container.delete(force=True)
       await docker.close()

   if __name__ == '__main__':
       loop = asyncio.get_event_loop()
       loop.run_until_complete(list_things())
       loop.run_until_complete(run_container())
       loop.close()

