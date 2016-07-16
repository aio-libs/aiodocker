#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

loop = asyncio.get_event_loop()
docker = Docker()


@asyncio.coroutine
def handler(events):
    queue = events.listen()

    yield from docker.pull("debian:jessie")

    config = {
        "Cmd":["tail", "-f", "/var/log/dmesg"],
        "Image":"debian:jessie",
         "AttachStdin":False,
         "AttachStdout":True,
         "AttachStderr":True,
         "Tty":False,
         "OpenStdin":False,
         "StdinOnce":False,
    }

    container = yield from docker.containers.create_or_replace(config=config, name='testing')
    yield from container.start(config)

    while True:
        event = yield from queue.get()
        if event.get('status', None) == 'start':
            yield from event['container'].stop()
            print("Killed {id} so hard".format(**event))


events = docker.events
tasks = [asyncio.async(events.run()),
         asyncio.async(handler(events)),]

loop.run_until_complete(asyncio.gather(*tasks))
