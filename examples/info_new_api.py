#!/usr/bin/env python3

import asyncio
from aiodocker.client import DockerClient
from aiodocker.errors import ImageNotFound


async def demo(client):
    print('--------------------------------')
    print('- Check Docker Version Information')
    data_version = await client.version()
    for key, value in data_version.items():
        print(key, ':', value)

    print('--------------------------------')
    print('- Check Docker Image List')
    images = await client.images.list()
    for image in images:
        print('Id: {} RepoTags: {}'.format(image.short_id, image.tags))

    print('--------------------------------')
    print('- Check Docker Container List')
    containers = await client.containers.list()
    for container in containers:
        print('Id: {}  Name: {}'.format(container.id, container.name))
    print('--------------------------------')
    print('- Check for non-existing Image')
    try:
        await client.images.get('non-existing-image')
    except ImageNotFound as e:
        print(e)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    docker_client = DockerClient()
    try:
        loop.run_until_complete(demo(docker_client))
    finally:
        loop.run_until_complete(docker_client.close())
        loop.close()
