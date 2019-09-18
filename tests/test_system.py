import pytest


@pytest.mark.asyncio
async def test_system_info(docker):
    docker_info = await docker.system.info()
    assert "ID" in docker_info
    assert "ServerVersion" in docker_info
