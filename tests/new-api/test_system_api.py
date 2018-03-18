import pytest


@pytest.mark.asyncio
async def test_system_info(docker):
    docker_info = await docker.info()
    assert 'ID' in docker_info
    assert docker_info['ServerVersion'].startswith("1")
