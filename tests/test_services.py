import asyncio
import pytest
from aiodocker.exceptions import DockerError
import aiohttp


@pytest.mark.asyncio
async def test_swarm_init(docker):
    swarm = await docker.swarm.init()
    assert swarm


@pytest.mark.asyncio
async def test_service_create(docker):
    services = await docker.services.list()
    orig_count = len(services)

    assert orig_count == 0

    TaskTemplate = {
        "ContainerSpec": {
            "Image": "redis",
            },
        }

    for n in range(3):
        name = "service-{n}".format(n=n)
        service = await docker.services.create(
                            task_template=TaskTemplate,
                            name=name
                            )
        assert service

    services = await docker.services.list()
    assert len(services) == orig_count + 3


@pytest.mark.asyncio
async def test_service_inspect(docker):
    services = await docker.services.list()

    for service in services:
        await docker.services.inspect(service_id=service['ID'])


@pytest.mark.asyncio
async def test_service_list_with_filter(docker):
    services = await docker.services.list()

    for service in services:
        _id = service['ID']
        docker_service = await docker.services.inspect(service_id=_id)
        name = docker_service['Spec']['Name']
        filters = {"name": name}
        filtered_list = await docker.services.list(filters=filters)
        assert len(filtered_list) == 1


@pytest.mark.asyncio
async def test_service_tasks(docker):
    tasks = await docker.tasks.list()

    for task in tasks:
        inspected_task = await docker.tasks.inspect(task['ID'])
        assert inspected_task['ID'] == task['ID']

        filters = {"id": task['ID']}

        this_task = await docker.tasks.list(filters=filters)
        assert len(this_task) == 1


@pytest.mark.asyncio
async def test_delete_services(docker):
    services = await docker.services.list()

    for service in services:
        await docker.services.delete(service_id=service['ID'])


# temporary fix https://github.com/aio-libs/aiodocker/issues/53
@pytest.mark.xfail(raises=DockerError, reason="bug inside Docker")
@pytest.mark.asyncio
async def test_logs_services(docker, testing_images):
    TaskTemplate = {
        "ContainerSpec": {
            "Image": "python:3.6.1-alpine",
            "Args": ["python", "-c", "while True: print('Hello Python')"]
        }
    }
    service = await docker.services.create(
        task_template=TaskTemplate,
    )
    service_id = service['ID']

    response = await docker.services.logs(
                            service_id, stdout=True, stderr=True, follow=True
                            )
    found = False
    try:
        # collect the logs for at most
        # 10 secs until we see the output
        # services are `slower`
        with aiohttp.Timeout(10):
            async for log in response:
                if "Hello Python\n" == log:
                    found = True
    except asyncio.TimeoutError:
        pass
    assert found


@pytest.mark.asyncio
async def test_swarm_remove(docker):
    services = await docker.services.list()
    for service in services:
        await docker.services.delete(service_id=service['ID'])
    await docker.swarm.leave(force=True)
