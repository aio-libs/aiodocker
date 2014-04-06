#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

loop = asyncio.get_event_loop()
docker = Docker("http://localhost:4243/")


@asyncio.coroutine
def handler(events):
    queue = events.listen()

    # config = {
    #     "Cmd": ["bash"], "Image": "debian",
    # }
    # container = yield from docker.containers.start(config, name='testing')
    # print(container)

    while True:
        event = yield from queue.get()
        if event['status'] == 'create':
            yield from event['container'].stop()
            print("Killed {id} so hard".format(**event))


events = docker.events
tasks = [asyncio.async(events.run()),
         asyncio.async(handler(events)),]

loop.run_until_complete(asyncio.gather(*tasks))
