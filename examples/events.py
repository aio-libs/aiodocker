#!/usr/bin/env python3

import asyncio
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


async def demo(docker):
    try:
        await docker.images.get('alpine:latest')
    except DockerError as e:
        if e.status == 404:
            await docker.pull('alpine:latest')
        else:
            print('Error retrieving alpine:latest image.')
            return

    subscriber = docker.events.subscribe()

    config = {
        "Cmd": ["tail", "-f", "/var/log/dmesg"],
        "Image":"alpine:latest",
         "AttachStdin": False,
         "AttachStdout": True,
         "AttachStderr": True,
         "Tty": False,
         "OpenStdin": False,
         "StdinOnce": False,
    }
    container = await docker.containers.create_or_replace(
        config=config, name='testing')
    await container.start()
    print(f"=> created and started container {container._id[:12]}")

    while True:
        event = await subscriber.get()
        if event is None:
            break
        print(f"event: {event!r}")

        # Demonstrate simple event-driven container mgmt.
        if event['Actor']['ID'] == container._id:
            if event['Action'] == 'start':
                await container.stop()
                print(f"=> killed {container._id[:12]}")
            elif event['Action'] == 'stop':
                await container.delete(force=True)
                print(f"=> deleted {container._id[:12]}")
            elif event['Action'] == 'destroy':
                print('=> done with this container!')
                break

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        docker = Docker()
        # start a monitoring task.
        event_task = loop.create_task(docker.events.run())
        try:
            # do our stuffs.
            loop.run_until_complete(demo(docker))
        finally:
            # explicitly stop monitoring.
            event_task.cancel()
            loop.run_until_complete(docker.close())
            if not event_task.cancelled():
                event_task.result()  # NOTE: maybe raise an exception
    finally:
        loop.close()
