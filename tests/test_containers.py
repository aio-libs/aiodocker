import asyncio
import os

import pytest

from aiodocker.exceptions import DockerContainerError, DockerError


async def _validate_hello(container):
    try:
        await container.start()
        response = await container.wait()
        assert response["StatusCode"] == 0
        await asyncio.sleep(5)  # wait for output in case of slow test container
        logs = await container.log(stdout=True)
        assert "hello" + os.linesep in logs

        with pytest.raises(TypeError):
            await container.log()
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_run_existing_container(docker):
    name = "python:latest"
    await docker.pull(name)
    container = await docker.containers.run(
        config={"Cmd": ["-c", "print('hello')"], "Entrypoint": "python", "Image": name}
    )

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_container_with_missing_image(docker):
    name = "python:latest"
    try:
        await docker.images.delete(name)
    except DockerError as e:
        if e.status == 404:
            pass  # already missing, pass
        else:
            raise

    # should automatically pull the image
    container = await docker.containers.run(
        config={"Cmd": ["-c", "print('hello')"], "Entrypoint": "python", "Image": name}
    )

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_failing_start_container(docker):
    name = "python:latest"
    try:
        await docker.images.delete(name)
    except DockerError as e:
        if e.status == 404:
            pass  # already missing, pass
        else:
            raise

    with pytest.raises(DockerContainerError) as e_info:
        await docker.containers.run(
            config={
                # we want to raise an error
                # `executable file not found`
                "Cmd": ["pytohon", "-c" "print('hello')"],
                "Image": name,
            }
        )

    assert e_info.value.container_id
    # This container is created but not started!
    # We should delete it afterwards.
    cid = e_info.value.container_id
    container = docker.containers.container(cid)
    await container.delete()


@pytest.mark.asyncio
async def test_restart(docker):
    # sleep for 10 min to emulate hanging container
    container = await docker.containers.run(
        config={
            "Cmd": ["python", "-c", "import time;time.sleep(600)"],
            "Image": "python:latest",
        }
    )
    try:
        details = await container.show()
        assert details["State"]["Running"]
        startTime = details["State"]["StartedAt"]
        await container.restart(timeout=1)
        await asyncio.sleep(3)
        details = await container.show()
        assert details["State"]["Running"]
        restartTime = details["State"]["StartedAt"]

        assert restartTime > startTime

        await container.stop()
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_container_stats_list(docker):
    name = "python:latest"
    container = await docker.containers.run(
        config={"Cmd": ["-c", "print('hello')"], "Entrypoint": "python", "Image": name}
    )

    try:
        await container.start()
        response = await container.wait()
        assert response["StatusCode"] == 0
        stats = await container.stats(stream=False)
        assert "cpu_stats" in stats[0]
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_container_stats_stream(docker):
    name = "python:latest"
    container = await docker.containers.run(
        config={"Cmd": ["-c", "print('hello')"], "Entrypoint": "python", "Image": name}
    )

    try:
        await container.start()
        response = await container.wait()
        assert response["StatusCode"] == 0
        count = 0
        async for stat in container.stats():
            assert "cpu_stats" in stat
            count += 1
            if count > 3:
                break
    finally:
        await container.delete(force=True)
