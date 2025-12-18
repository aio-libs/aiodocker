.. aiodocker documentation master file, created by
   sphinx-quickstart on Sat Jul 15 11:34:21 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=========================================
aiodocker: AsyncIO bindings for docker.io
=========================================


.. image:: https://badge.fury.io/py/aiodocker.svg
   :target: https://badge.fury.io/py/aiodocker
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/aiodocker.svg
   :target: https://pypi.org/project/aiodocker/
   :alt: Python Versions

.. image:: https://github.com/aio-libs/aiodocker/actions/workflows/ci-cd.yml/badge.svg?branch=main
   :target: https://github.com/aio-libs/aiodocker/actions/workflows/ci-cd.yml?query=branch%3Amain
   :alt: GitHub Actions status for the main branch

.. image:: https://codecov.io/gh/aio-libs/aiodocker/branch/main/graph/badge.svg
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


Examples
========

.. code-block:: python

    import asyncio
    import aiodocker

    async def list_things(docker):
        print('== Images ==')
        for image in (await docker.images.list()):
            tags = image['RepoTags'][0] if image['RepoTags'] else ''
            print(image['Id'], tags)
        print('== Containers ==')
        for container in (await docker.containers.list()):
            print(f" {container._id}")

    async def run_container(docker):
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

    async def main():
        docker = aiodocker.Docker()
        await list_things(docker)
        await run_container(docker)
        await docker.close()

    if __name__ == "__main__":
        asyncio.run(main())


Source code
-----------

The project is hosted on GitHub: https://github.com/aio-libs/aiodocker

Please feel free to file an issue on the bug tracker if you have found
a bug or have some suggestion in order to improve the library.


Communication channels
----------------------

*aio-libs* google group: https://groups.google.com/forum/#!forum/aio-libs

Feel free to post your questions and ideas here.

*Gitter Chat* https://gitter.im/aio-libs/Lobby

We support `Stack Overflow <https://stackoverflow.com>`_.
Please add *python-asyncio* tag to your question there.


Contribution
------------

Please follow the `Contribution Guide <https://github.com/aio-libs/aiodocker/wiki>`_.


Author and License
-------------------

The ``aiodocker`` package is written by Andrew Svetlov.

It's *Apache 2* licensed and freely available.


.. toctree::
   :hidden:
   :maxdepth: 2

   client
   configs
   containers
   exec
   stream
   logs
   images
   networks
   secrets
   services
   ssh
   swarm
   system
   volumes
   tasks
   events
   types
   exceptions

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
