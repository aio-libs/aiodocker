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

    config = {
        "Cmd": ["/bin/ash"],
        "Image": "alpine:latest",
         "AttachStdin": True,
         "AttachStdout": True,
         "AttachStderr": True,
         "Tty": False,
         "OpenStdin": True,
         "StdinOnce": True,
    }
    container = await docker.containers.create_or_replace(
        config=config, name='aiodocker-example')
    await container.start(config)
    print(f"created and started container {container._id[:12]}")

    ws = await container.websocket(stdin=True, stdout=True, stream=True)
    ws.send_str('echo hello world\n')
    resp = await ws.receive()
    print(f"received: {resp}")
    await ws.close()

    output = await container.log(stdout=True)
    print(f"log output: {output}")

    try:
        await container.wait(timeout=1)
    except asyncio.TimeoutError:
        pass

    print("removing container")
    await container.delete(force=True)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    docker = Docker()
    try:
        loop.run_until_complete(demo(docker))
    finally:
        loop.run_until_complete(docker.close())
        loop.close()
