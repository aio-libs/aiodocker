import aiohttp
import asyncio
import pytest
from distutils.version import StrictVersion


TaskTemplate = {
    "ContainerSpec": {
        "Image": "redis",
        },
    }


async def _wait_service(swarm, service_id):
    for i in range(5):
        tasks = await swarm.tasks.list(filters={'service': service_id})
        if tasks:
            return
        await asyncio.sleep(0.2)
    raise RuntimeError("Waited service %s for too long" % service_id)


@pytest.fixture
def tmp_service(event_loop, swarm, random_name):
    service = event_loop.run_until_complete(
        swarm.services.create(task_template=TaskTemplate, name=random_name()))
    event_loop.run_until_complete(_wait_service(swarm, service['ID']))
    yield service['ID']
    event_loop.run_until_complete(swarm.services.delete(service['ID']))


@pytest.mark.asyncio
async def test_service_list_with_filter(swarm, tmp_service):
    docker_service = await swarm.services.inspect(service_id=tmp_service)
    name = docker_service['Spec']['Name']
    filters = {"name": name}
    filtered_list = await swarm.services.list(filters=filters)
    assert len(filtered_list) == 1


@pytest.mark.asyncio
async def test_service_tasks(swarm, tmp_service):
    assert await swarm.tasks.list()
    tasks = await swarm.tasks.list(filters={'service': tmp_service})
    assert len(tasks) == 1
    assert tasks[0]['ServiceID'] == tmp_service
    assert await swarm.tasks.inspect(tasks[0]['ID'])


@pytest.mark.asyncio
async def test_logs_services(swarm):
    if StrictVersion(swarm.api_version[1:]) < StrictVersion("1.29"):
        pytest.skip("The feature is experimental before API version 1.29")

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
    service = await swarm.services.create(
        task_template=TaskTemplate,
    )
    service_id = service['ID']

    filters = {"service": service_id}

    # wait till task status is `complete`
    with aiohttp.Timeout(60):
        while True:
            await asyncio.sleep(2)
            task = await swarm.tasks.list(filters=filters)
            if task:
                status = task[0]['Status']['State']
                if status == 'complete':
                    break

    logs = await swarm.services.logs(
                            service_id, stdout=True)

    assert len(logs) == 10
    assert logs[0] == "Hello Python"


@pytest.mark.asyncio
async def test_logs_services_stream(swarm):
    if StrictVersion(swarm.api_version[1:]) < StrictVersion("1.29"):
        pytest.skip("The feature is experimental before API version 1.29")

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
    service = await swarm.services.create(
        task_template=TaskTemplate,
    )
    service_id = service['ID']

    filters = {"service": service_id}

    # wait till task status is `complete`
    with aiohttp.Timeout(60):
        while True:
            await asyncio.sleep(2)
            task = await swarm.tasks.list(filters=filters)
            if task:
                status = task[0]['Status']['State']
                if status == 'complete':
                    break

    stream = await swarm.services.logs(
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
