import asyncio
import datetime
import io
import os
import sys
import tarfile
import time
from distutils.version import StrictVersion

import aiohttp
import pytest

from aiodocker.docker import Docker


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
        await docker.containers.list()
    await docker.close()


@pytest.mark.asyncio
async def test_connect_envvar(monkeypatch):
    monkeypatch.setenv('DOCKER_HOST',
                       'unix:///var/run/does-not-exist-docker.sock')
    docker = Docker()
    assert isinstance(docker.connector, aiohttp.connector.UnixConnector)
    assert docker.docker_host == 'unix://localhost'
    with pytest.raises(aiohttp.ClientOSError):
        await docker.containers.list()
    await docker.close()

    monkeypatch.setenv('DOCKER_HOST', 'http://localhost:9999')
    docker = Docker()
    assert isinstance(docker.connector, aiohttp.TCPConnector)
    assert docker.docker_host == 'http://localhost:9999'
    with pytest.raises(aiohttp.ClientOSError):
        await docker.containers.list()
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
    await f_container.show()

    for container in my_containers:
        await container.delete(force=True)

    containers = await docker.containers.list(all=True)
    assert len(containers) == orig_count


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == 'darwin',
                    reason="Docker for Mac has a bug with websocket")
async def test_stdio_stdin(docker, testing_images, shell_container):
    if StrictVersion(docker.api_version[1:]) < StrictVersion("1.28"):
        pytest.skip("The WebSocket return text before API version 1.28")

    # echo of the input.
    ws = await shell_container.websocket(stdin=True, stdout=True, stream=True)
    await ws.send_str('echo hello world\n')
    output = b''
    found = False
    try:
        # collect the websocket outputs for at most 2 secs until we see the
        # output.
        with aiohttp.Timeout(2):
            while True:
                output += await ws.receive_bytes()
                if b"echo hello world\r\n" in output:
                    found = True
                    break
    except asyncio.TimeoutError:
        pass
    await ws.close()
    if not found:
        found = b"echo hello world\r\n" in output
    assert found

    # cross-check with container logs.
    log = []
    found = False

    try:
        # collect the logs for at most 2 secs until we see the output.
        stream = await shell_container.log(stdout=True, follow=True)
        with aiohttp.Timeout(2):
            async for s in stream:
                log.append(s)
                if "hello world\r\n" in s:
                    found = True
                    break
    except asyncio.TimeoutError:
        pass
    if not found:
        output = ''.join(log)
        output.strip()
        found = "hello world" in output.split('\r\n')
    assert found


@pytest.mark.asyncio
async def test_wait_timeout(docker, testing_images, shell_container):
    t1 = datetime.datetime.now()
    with pytest.raises(asyncio.TimeoutError):
        await shell_container.wait(timeout=0.5)
    t2 = datetime.datetime.now()
    delta = t2 - t1
    assert delta.total_seconds() < 5


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
    await container.put_archive(
        path='/tmp',
        data=file_like_object.getvalue())
    await container.start()
    await container.wait(timeout=5)

    output = await container.log(stdout=True, stderr=True)
    assert output[0] == "hello world"

    await container.delete(force=True)


@pytest.mark.asyncio
async def test_get_archive(docker, testing_images):
    config = {
        "Cmd": ["ash", "-c", "echo 'test' > /tmp/foo.txt"],
        "Image": "alpine:latest",
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": True,
        "OpenStdin": False
    }

    container = await docker.containers.create_or_replace(
        config=config,
        name='aiodocker-testing-get-archive')
    await container.start()
    tar_archive = await container.get_archive('/tmp/foo.txt')

    assert tar_archive is not None
    assert len(tar_archive.members) == 1
    foo_file = tar_archive.extractfile('foo.txt')
    assert foo_file.read() == b'test\n'
    await container.delete(force=True)


@pytest.mark.asyncio
async def test_port(docker, testing_images, redis_container):
    port = await redis_container.port(6379)
    assert port


@pytest.mark.asyncio
async def test_events(docker, testing_images, event_loop):
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

    await docker.events.stop()
