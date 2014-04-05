#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker
from aiodocker.channel import Channel

# docker = Docker("http://localhost:4243/")
# 
# 
# @asyncio.coroutine
# def callback(event):
#     if event['status'] == 'create':
#         x = yield from docker.kill_container(event['id'])
#         print("Haha, try again, sucker. {id}".format(**event))



@asyncio.coroutine
def testing():
    channel = Channel()
    bits = [asyncio.async(consumer(channel.open()))
            for _ in range(10)]
    yield from channel.put("test2")
    yield from channel.put("test1")
    yield from channel.put("test3")
    yield from channel.put("test4")
    yield from asyncio.gather(*bits)


@asyncio.coroutine
def consumer(cit):
    while True:
        data = yield from cit.get()
        print("Got", data)
        yield from asyncio.sleep(1)
    print("End of consumer")


loop = asyncio.get_event_loop()
loop.run_until_complete(testing())
