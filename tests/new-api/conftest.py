import asyncio
import uuid
from distutils.version import StrictVersion
from os import environ as ENV
import traceback

import pytest

from aiodocker.client import DockerClient
from aiodocker.errors import NotFound, ImageNotFound, APIError


_api_versions = {
    "17.06": "v1.30",
}


def _random_name():
    return "aiodocker-" + uuid.uuid4().hex[:7]


@pytest.fixture(scope='session')
def random_name():
    yield _random_name

    # If some test cases have used randomly-named temporary images,
    # we need to clean up them!
    if ENV.get('CI', '') == 'true':
        # But inside the CI server, we don't need clean up!
        return
    event_loop = asyncio.get_event_loop()

    async def _clean():
        docker_client = DockerClient()
        images = await docker_client.images.list()
        for img in images:
            if not img.tags:
                continue
            try:
                if img.tags[0].startswith('aiodocker-'):
                    print('Deleting image id: {0}'.format(img.id))
                    await docker_client.images.remove(img.id, force=True)
            except APIError as e:
                traceback.print_exc()
        await docker_client.close()

    event_loop.run_until_complete(_clean())


@pytest.fixture(scope='session')
def testing_images():
    # Prepare a small Linux image shared by most test cases.
    event_loop = asyncio.get_event_loop()

    async def _pull():
        docker_client = DockerClient()
        required_images = [
            'alpine:latest',
            'redis:latest',
            'redis:3.0.2',
            'redis:4.0',
            'python:3.6.1-alpine',
        ]
        for img in required_images:
            try:
                await docker_client.images.get(img)
            except ImageNotFound:
                print('Pulling "{img}" for the testing session...'.format(img=img))
                await docker_client.images.pull(img)
        await docker_client.close()

    event_loop.run_until_complete(_pull())


@pytest.fixture
def docker(event_loop, testing_images):
    kwargs = {}
    if "DOCKER_VERSION" in ENV:
        kwargs["api_version"] = _api_versions[ENV["DOCKER_VERSION"]]
    docker = DockerClient(**kwargs)
    yield docker

    async def _finalize():
        await docker.close()
    event_loop.run_until_complete(_finalize())


@pytest.fixture
def requires_api_version(docker):
    event_loop = asyncio.get_event_loop()

    async def _get_version():
        return await docker.version()

    _version = event_loop.run_until_complete(_get_version())

    def check(version, reason):
        if StrictVersion(_version[1:]) < StrictVersion(version[1:]):
            pytest.skip(reason)

    yield check


@pytest.fixture
def swarm(event_loop, docker):
    assert event_loop.run_until_complete(docker.swarm.init())
    yield docker
    assert event_loop.run_until_complete(docker.swarm.leave(force=True))


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
        container = await docker.containers.create(
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
        container = await docker.containers.create(
            config=config,
            name='aiodocker-testing-redis')
        await container.start()
    event_loop.run_until_complete(_spawn())

    yield container

    async def _delete():
        nonlocal container
        await container.delete(force=True)
    event_loop.run_until_complete(_delete())
