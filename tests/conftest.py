import asyncio
import uuid
from distutils.version import StrictVersion
from os import environ as ENV
import traceback

import pytest

from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


_api_versions = {
    "17.06": "v1.30",
    "17.05": "v1.29",
    "17.04": "v1.28",
    "17.03": "v1.27",
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
        docker = Docker()
        images = await docker.images.list()
        for img in images:
            if img['RepoTags'] is None:
                continue
            try:
                if img['RepoTags'][0].startswith('aiodocker-'):
                    print('Deleting image id: {0}'.format(img['Id']))
                    await docker.images.delete(img['Id'], force=True)
            except DockerError as e:
                traceback.print_exc()
        await docker.close()

    event_loop.run_until_complete(_clean())


@pytest.fixture(scope='session')
def testing_images():
    # Prepare a small Linux image shared by most test cases.
    event_loop = asyncio.get_event_loop()

    async def _pull():
        docker = Docker()
        required_images = [
            'alpine:latest', 'redis:latest', 'python:3.6.1-alpine',
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
def docker(event_loop, testing_images):
    kwargs = {}
    if "DOCKER_VERSION" in ENV:
        kwargs["api_version"] = _api_versions[ENV["DOCKER_VERSION"]]
    docker = Docker(**kwargs)
    yield docker

    async def _finalize():
        await docker.close()
    event_loop.run_until_complete(_finalize())


@pytest.fixture
def requires_api_version(docker):

    def check(version, reason):
        if StrictVersion(docker.api_version[1:]) < StrictVersion(version[1:]):
            pytest.skip(reason)

    yield check


@pytest.fixture
def swarm(event_loop, docker):
    if StrictVersion(docker.api_version[1:]) < StrictVersion("1.28"):
        pytest.skip("The feature is experimental before API version 1.28")
    assert event_loop.run_until_complete(docker.swarm.init())
    yield docker
    try:
        assert event_loop.run_until_complete(docker.swarm.leave(force=True))
    except DockerError as exc:
        if StrictVersion(docker.api_version[1:]) >= StrictVersion("1.30"):
            raise
        else:
            # NOTE: in Docker version 1.28 and 1.29, it is possible that Docker
            #       refuses to leave the Swarm cleanly. Reducing the number
            #       of service ran seems to solve the issue. More at #53
            assert event_loop.run_until_complete(
                docker.swarm.leave(force=True))


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
