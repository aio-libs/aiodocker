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
async def test_logs_services(docker, testing_images):
    TaskTemplate = {
        "ContainerSpec": {
            "Image": "python:3.6.1-alpine",
            "Args": [
                "python", "-c",
                "for _ in range(10): print('Hello Python')"
                ]
        },
        "RestartPolicy": {
            "Condition": "none"
            }
    }
    service = await docker.services.create(
        task_template=TaskTemplate,
    )
    service_id = service['ID']

    filters = {"service": service_id}

    # wait till task status is `complete`
    with aiohttp.Timeout(60):
        while True:
            await asyncio.sleep(2)
            task = await docker.tasks.list(filters=filters)
            if task:
                status = task[0]['Status']['State']
                if status == 'complete':
                    break

    logs = await docker.services.logs(
                            service_id, stdout=True)

    assert len(logs) == 10
    assert logs[0] == "Hello Python"


@pytest.mark.asyncio
async def test_logs_services_stream(docker, testing_images):
    TaskTemplate = {
        "ContainerSpec": {
            "Image": "python:3.6.1-alpine",
            "Args": [
                "python", "-c",
                "for _ in range(10): print('Hello Python')"
                ]
        },
        "RestartPolicy": {
            "Condition": "none"
            }
    }
    service = await docker.services.create(
        task_template=TaskTemplate,
    )
    service_id = service['ID']

    filters = {"service": service_id}

    # wait till task status is `complete`
    with aiohttp.Timeout(60):
        while True:
            await asyncio.sleep(2)
            task = await docker.tasks.list(filters=filters)
            if task:
                status = task[0]['Status']['State']
                if status == 'complete':
                    break

    stream = await docker.services.logs(
                            service_id, stdout=True, follow=True
                            )

    # the service printed 10 `Hello Python`
    # let's check for them
    count = 0
    try:
        with aiohttp.Timeout(2):
            while True:
                async for log in stream:
                    if "Hello Python\n" in log:
                        count += 1
    except asyncio.TimeoutError:
        pass

    assert count == 10


@pytest.mark.asyncio
async def test_service_delete(docker):
    services = await docker.services.list()
    for service in services:
        await docker.services.delete(service_id=service['ID'])


# temporary fix https://github.com/aio-libs/aiodocker/issues/53
@pytest.mark.xfail(raises=DockerError, reason="bug inside Docker")
@pytest.mark.asyncio
async def test_swarm_remove(docker):
    await docker.swarm.leave(force=True)
