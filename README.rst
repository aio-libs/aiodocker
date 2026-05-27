==============================
AsyncIO bindings for docker.io
==============================

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


Development
===========

The recommended developer setup uses `uv <https://docs.astral.sh/uv/>`_, which
manages the virtualenv and resolves dependencies from the committed
``uv.lock`` so every contributor and CI job builds against the same versions.

.. code-block:: sh

   # Install uv first: https://docs.astral.sh/uv/getting-started/installation/
   uv sync --extra dev --extra lint --extra test --extra doc
   uv run pre-commit install

The ``Makefile`` helpers (``make develop``, ``make install``, ``make lint``,
``make test``) all assume uv.

Using pip instead (fallback)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you can't install uv, you can still bootstrap with pip. The resulting
environment isn't pinned to ``uv.lock``, so versions may drift from CI.

.. code-block:: sh

   python -m venv .venv && source .venv/bin/activate
   pip install -U pip
   pip install -e '.[dev,lint,test,doc]'  # in zsh, you need to escape brackets
   pre-commit install

Running tests
~~~~~~~~~~~~~

.. code-block:: sh

   # Run all tests
   make test

   # Run individual tests
   uv run pytest tests/test_images.py


Building packages
~~~~~~~~~~~~~~~~~

NOTE: Usually you don't need to run this step by yourself.

.. code-block:: sh

   uv build


Documentation
=============

http://aiodocker.readthedocs.io


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
