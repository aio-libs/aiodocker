import asyncio

from async_timeout import timeout
import pytest


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
async def test_service_tasks_list(swarm, tmp_service):
    tasks = await swarm.tasks.list()
    assert len(tasks) == 1
    assert tasks[0]['ServiceID'] == tmp_service
    assert await swarm.tasks.inspect(tasks[0]['ID'])


@pytest.mark.asyncio
async def test_service_tasks_list_with_filters(swarm, tmp_service):
    tasks = await swarm.tasks.list(filters={'service': tmp_service})
    assert len(tasks) == 1
    assert tasks[0]['ServiceID'] == tmp_service
    assert await swarm.tasks.inspect(tasks[0]['ID'])


@pytest.mark.asyncio
async def test_logs_services(swarm):
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
    with timeout(60):
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
    with timeout(60):
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
        with timeout(2):
            while True:
                async for log in stream:
                    if "Hello Python\n" in log:
                        count += 1
    except asyncio.TimeoutError:
        pass

    assert count == 10


@pytest.mark.asyncio
async def test_service_update(swarm):
    name = "service-update"
    initial_image = "redis:3.0.2"
    image_after_update = "redis:4.0"
    TaskTemplate = {
        "ContainerSpec": {
            "Image": initial_image,
        },
    }

    await swarm.services.create(
        name=name,
        task_template=TaskTemplate,
    )
    service = await swarm.services.inspect(name)
    current_image = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
    version = service['Version']['Index']
    assert initial_image in current_image

    # update the service
    await swarm.services.update(
        service_id=name, version=version, image=image_after_update
    )
    # wait a few to complete the update of the service
    await asyncio.sleep(1)

    service = await swarm.services.inspect(name)
    current_image = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
    version = service['Version']['Index']
    assert image_after_update in current_image

    # rollback to the previous one
    await swarm.services.update(
        service_id=name, version=version, rollback=True
    )
    service = await swarm.services.inspect(name)
    current_image = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
    assert initial_image in current_image

    await swarm.services.delete(name)


@pytest.mark.asyncio
async def test_service_update_error(swarm):
    name = "service-update"
    TaskTemplate = {
        "ContainerSpec": {
            "Image": "redis:3.0.2",
        },
    }
    await swarm.services.create(
        name=name,
        task_template=TaskTemplate,
    )
    await asyncio.sleep(1)
    service = await swarm.services.inspect(name)
    version = service['Version']['Index']

    with pytest.raises(ValueError):
        await swarm.services.update(service_id=name, version=version)

    await swarm.services.delete(name)


@pytest.mark.asyncio
async def test_service_create_error(swarm):
    name = "service-test-error"
    TaskTemplate = {
        "ContainerSpec": {
        },
    }
    with pytest.raises(KeyError):
        await swarm.services.create(
            name=name,
            task_template=TaskTemplate,
        )
