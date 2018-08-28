import pytest
import os


@pytest.mark.asyncio
async def test_system_info(docker):
    docker_info = await docker.system.info()
    assert 'ID' in docker_info
    docker_version = os.getenv("DOCKER_VERSION")
    assert docker_version in docker_info['ServerVersion']
