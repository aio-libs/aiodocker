import asyncio
import os
import sys
import traceback
import uuid
from distutils.version import StrictVersion
from typing import Any, Dict

import pytest

from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


API_VERSIONS = {
    "17.06": "v1.30",
    "17.09": "v1.32",
    "17.12": "v1.35",
    "18.02": "v1.36",
    "18.03": "v1.37",
    "18.06": "v1.38",
    "18.09": "v1.39",
}


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
    if os.environ.get("CI", "") == "true":
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
def image_name() -> str:
    if sys.platform == "win32":
        return "python:latest"
    else:
        return "python:alpine"


@pytest.fixture(scope="session")
def testing_images(image_name: str) -> None:
    # Prepare a small Linux image shared by most test cases.
    event_loop = asyncio.get_event_loop()

    async def _pull():
        docker = Docker()
        required_images = [image_name]
        if image_name != "python:latest":
            required_images.append("python:latest")
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
    version = os.environ.get("DOCKER_VERSION")
    if version:
        for k, v in API_VERSIONS.items():
            if version.startswith(k):
                kwargs["api_version"] = v
                break
        else:
            raise RuntimeError(f"Cannot find docker API version for {version}")

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
    if sys.platform == "win32":
        pytest.skip("swarm commands dont work on Windows")
    assert event_loop.run_until_complete(docker.swarm.init())
    yield docker
    assert event_loop.run_until_complete(docker.swarm.leave(force=True))


@pytest.fixture
def make_container(event_loop, docker):
    container = None

    async def _spawn(config: Dict[str, Any], name=None):
        nonlocal container
        container = await docker.containers.create_or_replace(config=config, name=name)
        await container.start()
        return container

    yield _spawn

    async def _delete():
        nonlocal container
        if container is not None:
            await container.delete(force=True)

    event_loop.run_until_complete(_delete())


@pytest.fixture
async def shell_container(event_loop, docker, make_container, image_name):
    config = {
        "Cmd": ["python"],
        "Image": image_name,
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": True,
        "OpenStdin": True,
    }

    return await make_container(config, name="aiodocker-testing-shell")
