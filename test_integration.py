import asyncio
import pytest
import tarfile
import time
import io
from io import StringIO
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


@pytest.mark.asyncio
def test_stdio_stdin():
    docker = Docker()

    yield from docker.pull("debian:jessie")

    config = {
        "Cmd":["sh"],
        "Image":"debian:jessie",
         "AttachStdin":True,
         "AttachStdout":True,
         "AttachStderr":True,
         "Tty":False,
         "OpenStdin":True,
         "StdinOnce":True,
    }


    container = yield from docker.containers.create_or_replace(config=config, name='testing')
    yield from container.start(config)

    ws = yield from container.websocket(stdin=True, stdout=True, stream=True)
    ws.send_str('echo hello world\n')
    resp = yield from ws.receive()
    assert resp.data == "hello world\n"
    ws.close()

    output = yield from container.log(stdout=True)
    print("log output:", output)
    assert output == "hello world\n"

    #TODO ensure container stopped on its own because stdin was closed

    print("removing container")
    yield from container.delete(force=True)


@pytest.mark.asyncio
def test_wait_timeout():
    docker = Docker()

    yield from docker.pull("debian:jessie")

    config = {
        "Cmd":["sh"],
        "Image":"debian:jessie",
         "AttachStdin":True,
         "AttachStdout":True,
         "AttachStderr":True,
         "Tty":False,
         "OpenStdin":True,
         "StdinOnce":True,
    }

    container = yield from docker.containers.create_or_replace(config=config, name='testing')
    yield from container.start(config)

    print("waiting for container to stop")
    try:
        yield from container.wait(timeout=1)
    except TimeoutError:
        pass
    else:
        assert "TimeoutError should have occured"

    print("removing container")
    yield from container.delete(force=True)

@pytest.mark.asyncio
def test_put_archive():
    docker = Docker()

    yield from docker.pull("debian:jessie")

    config = {
        "Cmd":["cat", "/tmp/bar/foo.txt"],
        #"Cmd":["ls", "-l", "/tmp"],
        "Image":"debian:jessie",
         "AttachStdin":True,
         "AttachStdout":True,
         "AttachStderr":True,
         "Tty":False,
         "OpenStdin":False
    }

    file_data = b"hello world"
    file_like_object = io.BytesIO()
    tar = tarfile.open(fileobj=file_like_object, mode='w')

    info = tarfile.TarInfo(name='bar')
    info.type = tarfile.DIRTYPE
    info.mode = 493 #755 oct -> dec
    info.mtime = time.time()
    tar.addfile(tarinfo=info)

    tarinfo = tarfile.TarInfo(name="bar/foo.txt")
    tarinfo.size = len(file_data)
    tar.addfile(tarinfo, io.BytesIO(file_data))
    tar.list()
    tar.close()

    container = yield from docker.containers.create_or_replace(config=config, name='testing')
    result = yield from container.put_archive(path='/tmp', data=file_like_object.getvalue())
    #print("put archive response:", result)
    yield from container.start(config)

    yield from container.wait(timeout=1)

    output = yield from container.log(stdout=True, stderr=True)
    print("log output:", output)
    assert output == "hello world\n"

    print("removing container")
    yield from container.delete(force=True)

@pytest.mark.asyncio
def test_port():
    docker = Docker()

    yield from docker.pull("redis:latest")

    config = {
        "Image":"redis:latest",
        "PublishAllPorts": True,
    }

    container = yield from docker.containers.create_or_replace(config=config, name='testing')
    #print("put archive response:", result)
    yield from container.start(config)

    port = yield from container.port(6379)

    print(container._container.get("NetworkSettings"))

    assert port

    yield from container.delete(force=True)

@pytest.mark.asyncio
def test_events():
    docker = Docker()
    queue = yield from docker.events.query()

    yield from docker.pull("debian:jessie")

    config = {
        "Cmd":["sh"],
        "Image":"debian:jessie",
    }

    container = yield from docker.containers.create_or_replace(config=config, name='testing')
    #print("put archive response:", result)
    yield from container.start(config)

    i = yield from queue.__aiter__()
    while True:
        try:
            event = yield from asyncio.wait_for(i.__anext__(), 2)
        except StopAsyncIteration:
            assert False, "Event queue should not terminate"
        else:
            if event.get('status', None) == 'start':
                if event['id'] == container._id:
                    yield from container.stop()
                    break

    yield from container.delete(force=True)
