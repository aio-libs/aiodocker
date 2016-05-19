#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker
from concurrent.futures import TimeoutError

loop = asyncio.get_event_loop()
docker = Docker()


@asyncio.coroutine
def handler():
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
    print("received:", resp)
    ws.close()

    output = yield from container.log(stdout=True)
    print("log output:", output)

    print("waiting for container to stop")
    try:
        yield from container.wait(timeout=1)
    except TimeoutError:
        pass

    print("removing container")
    yield from container.delete(force=True)


tasks = [asyncio.async(handler()),]

loop.run_until_complete(asyncio.gather(*tasks))
