#!/usr/bin/env python3

import asyncio

from aiodocker.docker import Docker


async def demo(docker):
    print("--------------------------------")
    print("- Check Docker Version Information")
    data_version = await docker.version()
    for key, value in data_version.items():
        print(key, ":", value)

    print("--------------------------------")
    print("- Check Docker Image List")
    images = await docker.images.list()
    for image in images:
        for key, value in image.items():
            if key == "RepoTags":
                print(key, ":", value)

    print("--------------------------------")
    print("- Check Docker Container List")
    containers = await docker.containers.list()
    for container in containers:
        container_show = await container.show()
        for key, value in container_show.items():
            if key == "Id":
                print("Id", ":", value[:12])
    print("--------------------------------")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    docker = Docker()
    try:
        loop.run_until_complete(demo(docker))
    finally:
        loop.run_until_complete(docker.close())
        loop.close()
