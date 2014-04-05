#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

loop = asyncio.get_event_loop()
docker = Docker("http://localhost:4243/")


@asyncio.coroutine
def handler(events):
    queue = events.listen()
    containers = docker.containers()

    while True:
        event = yield from queue.get()
        if event['status'] == 'create':
            yield from containers.stop(event['id'])
            print("Killed {id} so hard".format(**event))
            container = yield from containers.show(event['id'])
            if container['State']['Running'] is True:
                print("     WE LEAKED {id}".format(**event))



events = docker.events()
tasks = [asyncio.async(events.run()),
         asyncio.async(handler(events)),]

loop.run_until_complete(asyncio.gather(*tasks))
