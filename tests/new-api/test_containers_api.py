import asyncio
import pytest

from aiodocker.errors import ImageNotFound, APIError
from aiodocker.exceptions import DockerContainerError


async def _validate_hello(container):
    try:
        await container.start()
        response = await container.wait()
        assert response['StatusCode'] == 0
        logs = await container.logs(stdout=True)
        assert logs == ['hello']

        with pytest.raises(TypeError):
            await container.logs()
    finally:
        await container.remove(force=True)


@pytest.mark.asyncio
async def test_run_existing_container(docker):
    name = "alpine:latest"
    await docker.images.pull(name)
    container = await docker.containers.run(name, command=['-c', 'echo hello'], entrypoint='sh')

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_container_with_missing_image(docker):
    name = "alpine:latest"
    try:
        await asyncio.sleep(1)
        await docker.images.remove(name, force=True)
    except ImageNotFound as e:
        pass  # already missing, pass
    except APIError:
            raise

    # should automatically pull the image
    container = await docker.containers.run(name, command=['-c', 'echo hello'], entrypoint='sh')

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_failing_start_container(docker):
    name = "alpine:latest"
    try:
        await docker.images.remove(name, force=True)
    except ImageNotFound as e:
        pass  # already missing, pass
    except APIError:
            raise

    with pytest.raises(DockerContainerError) as e_info:
        # we want to raise an error
        # `executable file not found`
        await docker.containers.run(name, command=['pyton', 'echo hello'])

    assert e_info.value.container_id
    # This container is created but not started!
    # We should delete it afterwards.
    cid = e_info.value.container_id
    container = await docker.containers.get(cid)
    await container.remove()


@pytest.mark.asyncio
async def test_restart(docker):
    container = await docker.containers.run('gcr.io/google-containers/pause')
    try:
        container = await docker.containers.get(container.id)
        assert container.status == 'running'
        startTime = container.attrs['State']['StartedAt']
        await container.restart(timeout=1)
        await asyncio.sleep(3)
        container = await docker.containers.get(container.id)
        assert container.attrs['State']['Running']
        restartTime = container.attrs['State']['StartedAt']

        assert restartTime > startTime

        await container.stop()
    finally:
        await container.remove(force=True)
