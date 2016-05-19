#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

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

    print("waiting for container to stop")
    yield from container.wait(timeout=1)

    print("removing container")
    yield from container.remove(force=True)


tasks = [asyncio.async(handler()),]

loop.run_until_complete(asyncio.gather(*tasks))
