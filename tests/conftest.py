import asyncio
import sys
import traceback
import uuid
from distutils.version import StrictVersion
from os import environ as ENV

import pytest

from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


_api_versions = {"18.03.1": "v1.37", "17.12.1": "v1.35"}

if sys.platform == "win32":
    if sys.version_info < (3, 7):
        # Python 3.6 has no WindowsProactorEventLoopPolicy class
        from asyncio import events

        class WindowsProactorEventLoopPolicy(events.BaseDefaultEventLoopPolicy):
            _loop_factory = asyncio.ProactorEventLoop

    else:
        WindowsProactorEventLoopPolicy = asyncio.WindowsProactorEventLoopPolicy

    asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())


def _random_name():
    return "aiodocker-" + uuid.uuid4().hex[:7]


@pytest.fixture(scope="session")
def random_name():
    yield _random_name

    # If some test cases have used randomly-named temporary images,
    # we need to clean up them!
    if ENV.get("CI", "") == "true":
        # But inside the CI server, we don't need clean up!
        return
    event_loop = asyncio.get_event_loop()

    async def _clean():
        docker = Docker()
        images = await docker.images.list()
        for img in images:
            if img["RepoTags"] is None:
                continue
            try:
                if img["RepoTags"][0].startswith("aiodocker-"):
                    print("Deleting image id: {0}".format(img["Id"]))
                    await docker.images.delete(img["Id"], force=True)
            except DockerError:
                traceback.print_exc()
        await docker.close()

    event_loop.run_until_complete(_clean())


@pytest.fixture(scope="session")
def testing_images():
    # Prepare a small Linux image shared by most test cases.
    event_loop = asyncio.get_event_loop()

    async def _pull():
        docker = Docker()
        required_images = [
            "alpine:latest",
            "redis:latest",
            "redis:3.0.2",
            "redis:4.0",
            "python:3.6.1-alpine",
        ]
        for img in required_images:
            try:
                await docker.images.inspect(img)
            except DockerError as e:
                assert e.status == 404
                print('Pulling "{img}" for the testing session...'.format(img=img))
                await docker.pull(img)
        await docker.close()

    event_loop.run_until_complete(_pull())


@pytest.fixture
def docker(event_loop, testing_images):
    kwargs = {}
    if "DOCKER_VERSION" in ENV:
        kwargs["api_version"] = _api_versions[ENV["DOCKER_VERSION"]]

    async def _make_docker():
        return Docker(**kwargs)

    docker = event_loop.run_until_complete(_make_docker())
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
        container = await docker.containers.create_or_replace(
            config=config, name="aiodocker-testing-shell"
        )
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
    config = {"Image": "redis:latest", "PublishAllPorts": True}

    async def _spawn():
        nonlocal container
        container = await docker.containers.create_or_replace(
            config=config, name="aiodocker-testing-redis"
        )
        await container.start()

    event_loop.run_until_complete(_spawn())

    yield container

    async def _delete():
        nonlocal container
        await container.delete(force=True)

    event_loop.run_until_complete(_delete())
