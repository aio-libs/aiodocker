import asyncio
import os
import sys
import traceback
import uuid
from typing import Any, Dict

import pytest
from packaging.version import parse as parse_version

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


def _random_name():
    return "aiodocker-" + uuid.uuid4().hex[:7]


@pytest.fixture(scope="session")
async def random_name():
    yield _random_name

    # If some test cases have used randomly-named temporary images,
    # we need to clean up them!
    if os.environ.get("CI") is not None:
        # But inside the CI server, we don't need clean up!
        return

    docker = Docker()
    images = await docker.images.list()
    for img in images:
        if img["RepoTags"] is None:
            continue
        try:
            if img["RepoTags"][0].startswith("aiodocker-"):
                print("Deleting image id: {}".format(img["Id"]))
                await docker.images.delete(img["Id"], force=True)
        except DockerError:
            traceback.print_exc()
    await docker.close()


@pytest.fixture(scope="session")
def image_name() -> str:
    if sys.platform == "win32":
        return "python:latest"
    else:
        return "python:alpine"


@pytest.fixture(scope="session")
async def testing_images(image_name: str) -> None:
    # Prepare a small Linux image shared by most test cases.
    docker = Docker()
    required_images = [image_name]
    if image_name != "python:latest":
        required_images.append("python:latest")
    for img in required_images:
        try:
            await docker.images.inspect(img)
        except DockerError as e:
            assert e.status == 404
            print(f'Pulling "{img}" for the testing session...')
            await docker.pull(img)
    await docker.close()


@pytest.fixture
async def docker(testing_images):
    kwargs = {}
    version = os.environ.get("DOCKER_VERSION")
    if version:
        for k, v in API_VERSIONS.items():
            if version.startswith(k):
                kwargs["api_version"] = v
                break
        else:
            raise RuntimeError(f"Cannot find docker API version for {version}")

    docker = Docker(**kwargs)
    yield docker
    await docker.close()


@pytest.fixture
async def requires_api_version(docker):
    # Update version info from auto to the real value
    await docker.version()

    def check(version, reason):
        if parse_version(docker.api_version[1:]) < parse_version(version[1:]):
            pytest.skip(reason)

    yield check


@pytest.fixture
async def swarm(docker):
    if sys.platform == "win32":
        pytest.skip("swarm commands dont work on Windows")
    assert await docker.swarm.init()
    yield docker
    assert await docker.swarm.leave(force=True)


@pytest.fixture
async def make_container(docker):
    container = None

    async def _spawn(config: Dict[str, Any], name=None):
        nonlocal container
        container = await docker.containers.create_or_replace(config=config, name=name)
        await container.start()
        return container

    yield _spawn

    if container is not None:
        await container.delete(force=True)


@pytest.fixture
async def shell_container(docker, make_container, image_name):
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
