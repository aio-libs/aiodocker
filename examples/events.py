#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

loop = asyncio.get_event_loop()
docker = Docker("http://localhost:4243/")


@asyncio.coroutine
def handler(events):
    queue = events.listen()

    while True:
        event = yield from queue.get()
        print(event)


events = docker.events()
tasks = [asyncio.async(events.run()),
         asyncio.async(handler(events)),
         asyncio.async(handler(events)),]

loop.run_until_complete(asyncio.gather(*tasks))
