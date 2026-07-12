import pytest

from aiodocker.docker import Docker


@pytest.mark.asyncio
async def test_system_info(docker: Docker) -> None:
    docker_info = await docker.system.info()
    assert "ID" in docker_info
    assert "ServerVersion" in docker_info


@pytest.mark.asyncio
async def test_system_df(docker: Docker) -> None:
    usage = await docker.system.df()
    assert "LayersSize" in usage
    assert "Images" in usage


@pytest.mark.asyncio
async def test_system_df_types(docker: Docker) -> None:
    usage = await docker.system.df(types=["image"])
    assert "Images" in usage
