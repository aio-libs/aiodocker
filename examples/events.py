#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker

docker = Docker("http://localhost:4243/")


@asyncio.coroutine
def callback(event):
    if event['status'] == 'create':
        x = yield from docker.kill_container(event['id'])
        print("Haha, try again, sucker. {id}".format(**event))


loop = asyncio.get_event_loop()
loop.run_until_complete(docker.events(callback))
