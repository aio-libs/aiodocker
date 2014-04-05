#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

loop = asyncio.get_event_loop()
docker = Docker("http://localhost:4243/")


@asyncio.coroutine
def handler(events):
    print("waiting")
    queue = events.listen()
    while True:
        print("waiting")
        event = yield from queue.get()
        print(event)


@asyncio.coroutine
def main():
    events = docker.events()
    tasks = [
        asyncio.async(events.run()),
        asyncio.async(handler(events)),
        asyncio.async(handler(events)),
    ]
    yield from asyncio.gather(*tasks)


loop.run_until_complete(main())
