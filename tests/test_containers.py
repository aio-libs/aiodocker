import pytest

from aiodocker.exceptions import DockerError, DockerContainerError


async def _validate_hello(container):
    try:
        await container.start()
        response = await container.wait()
        assert response['StatusCode'] == 0
        logs = await container.log(stdout=True)
        assert logs == ['hello']

        with pytest.raises(TypeError):
            await container.log()
    finally:
        await container.delete(force=True)


@pytest.mark.asyncio
async def test_run_existing_container(docker):
    name = "alpine:latest"
    await docker.pull(name)
    container = await docker.containers.run(
        config={
            'Cmd': ['-c', 'echo hello'],
            'Entrypoint': 'sh',
            'Image': name
        }
    )

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_container_with_missing_image(docker):
    name = "alpine:latest"
    try:
        await docker.images.delete(name)
    except DockerError as e:
        if e.status == 404:
            pass  # already missing, pass
        else:
            raise

    # should automatically pull the image
    container = await docker.containers.run(
        config={
            'Cmd': ['-c', 'echo hello'],
            'Entrypoint': 'sh',
            'Image': name
        }
    )

    await _validate_hello(container)


@pytest.mark.asyncio
async def test_run_failing_start_container(docker):
    name = "alpine:latest"
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
                'Cmd': ['pyton', 'echo hello'],
                'Image': name
            }
        )

    assert e_info.value.container_id
    # This container is created but not started!
    # We should delete it afterwards.
    cid = e_info.value.container_id
    container = docker.containers.container(cid)
    await container.delete()
