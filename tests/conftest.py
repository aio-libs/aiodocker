from __future__ import annotations

import asyncio
import os
import secrets
import sys
from collections.abc import AsyncIterator, Iterator
from typing import Any, Callable

import pytest
from packaging.version import parse as parse_version
from testcontainers.core.container import DockerContainer as TempContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from aiodocker.containers import DockerContainer
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from aiodocker.types import AsyncContainerFactory


@pytest.fixture(scope="session")
async def random_name():
    random_image_name = "aiodocker-" + secrets.token_hex(4)
    yield random_image_name

    docker = Docker()
    try:
        image = await docker.images.inspect(random_image_name)
        print(f"Deleting image: {random_image_name} ({image['Id']})")
        await docker.images.delete(random_image_name, force=True)
    except DockerError as e:
        if e.status == 404:
            pass
        else:
            raise
    finally:
        await docker.close()


@pytest.fixture(scope="module")
def plain_registry() -> Iterator[TempContainer]:
    with TempContainer(
        "registry:2",
        name=f"aiodocker-test-registry-plain-{secrets.token_hex(4)}",
        ports=[5000],
        _wait_strategy=HttpWaitStrategy(5000).for_status_code(200),
    ) as plain_registry:
        yield plain_registry


@pytest.fixture(scope="module")
def secure_registry() -> Iterator[TempContainer]:
    with TempContainer(
        "registry:2",
        name=f"aiodocker-test-registry-secure-{secrets.token_hex(4)}",
        ports=[5001],
        volumes=[(f"{os.getcwd()}/tests/certs", "/certs", "ro")],
        env={
            "REGISTRY_AUTH": "htpasswd",
            "REGISTRY_AUTH_HTPASSWD_REALM": "Registry Realm",
            "REGISTRY_AUTH_HTPASSWD_PATH": "/certs/htpasswd",
            "REGISTRY_HTTP_ADDR": "0.0.0.0:5001",
            "REGISTRY_HTTP_TLS_CERTIFICATE": "/certs/registry.crt",
            "REGISTRY_HTTP_TLS_KEY": "/certs/registry.key",
        },
        _wait_strategy=(
            HttpWaitStrategy(5001).using_tls(insecure=True).for_status_code(200)
        ),
    ) as secure_registry:
        yield secure_registry


@pytest.fixture(scope="session")
def image_name() -> str:
    if sys.platform == "win32":
        return "python:3.13"
    return "python:3.13-alpine"


@pytest.fixture(scope="session")
def image_name_updated() -> str:
    if sys.platform == "win32":
        return "python:3.14"
    return "python:3.14-alpine"


@pytest.fixture(scope="session")
async def testing_images(image_name: str, image_name_updated: str) -> list[str]:
    images = [image_name, image_name_updated]
    for ref in images:
        proc = await asyncio.create_subprocess_exec("docker", "pull", ref)
        await proc.wait()
    return images


@pytest.fixture
async def docker(testing_images):
    # Create a new Docker client with the default configuration.
    docker = Docker()
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


@pytest.fixture
async def make_container(
    docker: Docker,
) -> AsyncIterator[AsyncContainerFactory]:
    container: DockerContainer | None = None

    async def _spawn(
        config: dict[str, Any],
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
            await container.delete(force=True)


@pytest.fixture
async def shell_container(
    docker: Docker,
    make_container: AsyncContainerFactory,
    image_name: str,
) -> DockerContainer:
    config = {
        "Cmd": ["python"],
        "Image": image_name,
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": True,
        "OpenStdin": True,
    }
    return await make_container(config, "aiodocker-testing-shell")
