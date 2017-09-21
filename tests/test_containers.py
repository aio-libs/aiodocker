import pytest


@pytest.mark.asyncio
async def test_run_container(docker):
    name = "alpine:latest"
    container = await docker.containers.run(
        config={
            'Cmd': ['-c', 'echo hello'],
            'Entrypoint': 'sh',
            'Image': name
        }
    )

    try:
        await container.start()
        response = await container.wait()
        assert response['StatusCode'] == 0
        logs = await container.log(stdout=True, stderr=True)
        assert logs == ['hello']
    finally:
        await container.delete(force=True)
