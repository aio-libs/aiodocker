import pytest


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
