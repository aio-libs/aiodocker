import pytest

from aiodocker.exceptions import DockerError


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
async def test_run_missing_container(docker):
    name = "alpine:latest"
    await docker.images.delete(name)

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
    with pytest.raises(DockerError) as e_info:
        name = "alpine:latest"
        await docker.images.delete(name)

        await docker.containers.run(
            config={
                # we want to raise an error
                # `executable file not found`
                'Cmd': ['pyton', 'echo hello'],
                'Image': name
            }
        )

    assert e_info.value.container_id
