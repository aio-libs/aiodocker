import asyncio
import pytest
from aiodocker.docker import Docker
from concurrent.futures import TimeoutError


@pytest.mark.asyncio
def test_container_lifecycles():
    docker = Docker()

    containers = yield from docker.containers.list(all=True)
    for container in containers:
        yield from container.delete(force=True)

    yield from docker.pull("debian:jessie")

    config = {
        "Cmd":["dmesg"],
        "Image":"debian:jessie",
         "AttachStdin":True,
         "AttachStdout":True,
         "AttachStderr":True,
         "Tty":False,
         "OpenStdin":False,
         "StdinOnce":False,
    }

    for i in range(3):
        container = yield from docker.containers.create(config=config)
        assert container

    containers = yield from docker.containers.list(all=True)
    assert len(containers) == 3

    f_container = containers[0]
    yield from f_container.start(config)
    info = yield from f_container.show()

    for container in containers:
        yield from container.delete(force=True)
