import asyncio
import io
import os
import sys
import tarfile
import time

import aiohttp
import pytest

from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


@pytest.mark.asyncio
async def test_autodetect_host(monkeypatch):
    docker = Docker()
    if 'DOCKER_HOST' in os.environ:
        if (os.environ['DOCKER_HOST'].startswith('http://') or
                os.environ['DOCKER_HOST'].startswith('https://') or
                os.environ['DOCKER_HOST'].startswith('tcp://')):
            assert docker.docker_host == os.environ['DOCKER_HOST']
        else:
            assert docker.docker_host == 'unix://localhost'
    else:
        # assuming that docker daemon is installed locally.
        assert docker.docker_host is not None
    await docker.close()


@pytest.mark.asyncio
async def test_connect_invalid_unix_socket():
    docker = Docker('unix:///var/run/does-not-exist-docker.sock')
    assert isinstance(docker.connector, aiohttp.connector.UnixConnector)
    with pytest.raises(aiohttp.ClientOSError):
        info = await docker.containers.list()
    await docker.close()


@pytest.mark.asyncio
async def test_connect_envvar(monkeypatch):
    monkeypatch.setenv('DOCKER_HOST', 'unix:///var/run/does-not-exist-docker.sock')
    docker = Docker()
    assert isinstance(docker.connector, aiohttp.connector.UnixConnector)
    assert docker.docker_host == 'unix://localhost'
    with pytest.raises(aiohttp.ClientOSError):
        info = await docker.containers.list()
    await docker.close()

    monkeypatch.setenv('DOCKER_HOST', 'http://localhost:9999')
    docker = Docker()
    assert isinstance(docker.connector, aiohttp.TCPConnector)
    assert docker.docker_host == 'http://localhost:9999'
    with pytest.raises(aiohttp.ClientOSError):
        info = await docker.containers.list()
    await docker.close()


@pytest.mark.asyncio
async def test_connect_with_connector(monkeypatch):
    connector = aiohttp.BaseConnector()
    docker = Docker(connector=connector)
    assert docker.connector == connector
    await docker.close()


@pytest.mark.asyncio
async def test_container_lifecycles(docker, testing_images):
    containers = await docker.containers.list(all=True)
    orig_count = len(containers)

    config = {
        "Cmd": ["/bin/ls"],
        "Image": "alpine:latest",
         "AttachStdin": False,
         "AttachStdout": False,
         "AttachStderr": False,
         "Tty": False,
         "OpenStdin": False,
    }

    my_containers = []
    for i in range(3):
        container = await docker.containers.create(config=config)
        assert container
        my_containers.append(container)

    containers = await docker.containers.list(all=True)
    assert len(containers) == orig_count + 3

    f_container = containers[0]
    await f_container.start()
    info = await f_container.show()

    for container in my_containers:
        await container.delete(force=True)

    containers = await docker.containers.list(all=True)
    assert len(containers) == orig_count


@pytest.mark.asyncio
@pytest.mark.xfail  # FIXME: docker websocket seems not working as expected
async def test_stdio_stdin(docker, testing_images, shell_container):
    ws = await shell_container.websocket(stdin=True, stdout=True, stream=True)
    await ws.send_str('echo "hello world"\n')
    with aiohttp.Timeout(2):
        # TODO: fix timeout
        resp = await ws.receive()
    print(resp)
    assert resp.data == b"hello world\n"
    await ws.close()
    # TODO: ensure container stopped on its own because stdin was closed

    # Cross-check container logs.
    output = await shell_container.log(stdout=True)
    output.strip()
    assert output == "hello world"


@pytest.mark.asyncio
async def test_wait_timeout(docker, testing_images, shell_container):
    with pytest.raises(asyncio.TimeoutError):
        await shell_container.wait(timeout=0.5)


@pytest.mark.asyncio
async def test_put_archive(docker, testing_images):
    config = {
        "Cmd": ["cat", "/tmp/bar/foo.txt"],
        "Image": "alpine:latest",
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": False,
        "OpenStdin": False
    }

    file_data = b"hello world"
    file_like_object = io.BytesIO()
    tar = tarfile.open(fileobj=file_like_object, mode='w')

    info = tarfile.TarInfo(name='bar')
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    info.mtime = time.time()
    tar.addfile(tarinfo=info)

    tarinfo = tarfile.TarInfo(name="bar/foo.txt")
    tarinfo.size = len(file_data)
    tar.addfile(tarinfo, io.BytesIO(file_data))
    tar.list()
    tar.close()

    container = await docker.containers.create_or_replace(
        config=config,
        name='aiodocker-testing-archive')
    result = await container.put_archive(
        path='/tmp',
        data=file_like_object.getvalue())
    await container.start()
    await container.wait(timeout=1)

    output = await container.log(stdout=True, stderr=True)
    output.strip()
    assert output == "hello world"

    await container.delete(force=True)


@pytest.mark.asyncio
async def test_port(docker, testing_images, redis_container):
    port = await redis_container.port(6379)
    assert port


@pytest.mark.asyncio
async def test_events(docker, testing_images, event_loop):
    monitor_task = event_loop.create_task(docker.events.run())
    subscriber = docker.events.subscribe()

    # Do some stuffs to generate events.
    config = {
        "Cmd": ["/bin/ash"],
        "Image": "alpine:latest",
    }
    container = await docker.containers.create_or_replace(
        config=config,
        name='aiodocker-testing-temp')
    await container.start()
    await container.delete(force=True)

    events_occurred = []
    while True:
        try:
            with aiohttp.Timeout(0.2):
                event = await subscriber.get()
            if event['Actor']['ID'] == container._id:
                events_occurred.append(event['Action'])
        except asyncio.TimeoutError:
            # no more events
            break
        except asyncio.CancelledError:
            break

    assert events_occurred == ['create', 'start', 'kill', 'die', 'destroy']
    monitor_task.cancel()
