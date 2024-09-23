from __future__ import annotations

import asyncio
import os
import sys
import traceback
import uuid
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
)

import pytest
from packaging.version import parse as parse_version

from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


if TYPE_CHECKING:
    if sys.version_info < (3, 10):
        from typing_extensions import TypeAlias
    else:
        from typing import TypeAlias


API_VERSIONS = {
    "17.06": "v1.30",
    "17.09": "v1.32",
    "17.12": "v1.35",
    "18.02": "v1.36",
    "18.03": "v1.37",
    "18.06": "v1.38",
    "18.09": "v1.39",
}


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
        if not img["RepoTags"]:
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
    return "python:alpine"


@pytest.fixture(scope="session")
async def testing_images(image_name: str) -> None:
    # Prepare a small Linux image shared by most test cases.
    docker = Docker()
    try:
        required_images = [image_name]
        for img in required_images:
            try:
                await docker.images.inspect(img)
            except DockerError as e:
                assert e.status == 404
                print(f'Pulling "{img}" for the testing session...')
                await docker.pull(img)
    finally:
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
    print(asyncio.get_running_loop())
    try:
        yield docker
    finally:
        await docker.close()


@pytest.fixture
async def requires_api_version(
    docker: Docker,
) -> AsyncIterator[Callable[[str, str], None]]:
    # Update version info from auto to the real value
    await docker.version()

    def check(version: str, reason: str) -> None:
        if parse_version(docker.api_version[1:]) < parse_version(version[1:]):
            pytest.skip(reason)

    yield check


@pytest.fixture
async def swarm(docker):
    if sys.platform == "win32":
        pytest.skip("swarm commands dont work on Windows")
    assert await docker.swarm.init()
    try:
        yield docker
    finally:
        assert await docker.swarm.leave(force=True)


AsyncContainerFactory: TypeAlias = Callable[
    [Dict[str, Any], str], Awaitable[DockerContainer]
]


@pytest.fixture
async def make_container(
    docker: Docker,
) -> AsyncIterator[AsyncContainerFactory]:
    container: DockerContainer | None = None

    async def _spawn(
        config: Dict[str, Any],
        name: str,
    ) -> DockerContainer:
        nonlocal container
        container = await docker.containers.create_or_replace(config=config, name=name)
        assert container is not None
        await container.start()
        return container

    try:
        yield _spawn
    finally:
        if container is not None:
            assert isinstance(container, DockerContainer)
            await container.delete(force=True)


@pytest.fixture
async def shell_container(
    docker: Docker,
    make_container,
    image_name: str,
) -> AsyncContainerFactory:
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
