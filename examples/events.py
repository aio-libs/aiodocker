#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker


docker = Docker("http://localhost:4243/")


@asyncio.coroutine
def callback(event):
    print(event)


loop = asyncio.get_event_loop()
loop.run_until_complete(docker.events(callback))
