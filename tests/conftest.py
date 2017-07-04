import asyncio

import pytest

from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


@pytest.fixture(scope='session')
def testing_images():
    # Prepare a small Linux image shared by most test cases.
    event_loop = asyncio.get_event_loop()

    async def _pull():
        docker = Docker()
        required_images = [
            'alpine:latest', 'redis:latest', 'python:3.6.1'
        ]
        for img in required_images:
            try:
                await docker.images.get(img)
            except DockerError as e:
                assert e.status == 404
                print('Pulling "{img}" for the testing session...'
                      .format(img=img))
                await docker.pull(img)
        await docker.close()
    event_loop.run_until_complete(_pull())


@pytest.fixture
def docker(event_loop):
    docker = Docker()
    yield docker

    async def _finalize():
        await docker.close()
    event_loop.run_until_complete(_finalize())


@pytest.fixture
def shell_container(event_loop, docker):
    container = None
    config = {
        "Cmd": ["/bin/ash"],
        "Image": "alpine:latest",
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": True,
        "OpenStdin": True,
    }

    async def _spawn():
        nonlocal container
        container = await docker.containers.create_or_replace(
            config=config,
            name='aiodocker-testing-shell')
        await container.start()
    event_loop.run_until_complete(_spawn())

    yield container

    async def _delete():
        nonlocal container
        await container.delete(force=True)
    event_loop.run_until_complete(_delete())


@pytest.fixture
def redis_container(event_loop, docker):
    container = None
    config = {
        "Image": "redis:latest",
        "PublishAllPorts": True,
    }

    async def _spawn():
        nonlocal container
        container = await docker.containers.create_or_replace(
            config=config,
            name='aiodocker-testing-redis')
        await container.start()
    event_loop.run_until_complete(_spawn())

    yield container

    async def _delete():
        nonlocal container
        await container.delete(force=True)
    event_loop.run_until_complete(_delete())
