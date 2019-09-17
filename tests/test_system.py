import pytest
import os


@pytest.mark.asyncio
async def test_system_info_id(docker):
    docker_info = await docker.system.info()
    assert "ID" in docker_info

@pytest.mark.asyncio
async def test_system_info_version(docker):
    docker_info = await docker.system.info()
    docker_version = os.getenv("DOCKER_VERSION")
    if docker_version is None:
        pytest.skip("DOCKER_VERSION env var is not set")
    assert docker_version in docker_info["ServerVersion"]
