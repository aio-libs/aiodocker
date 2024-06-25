import pytest

from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError


@pytest.mark.asyncio
async def test_create_search_get_delete(docker: Docker) -> None:
    name = "aiodocker-test-volume-two"
    await docker.volumes.create({
        "Name": name,
        "Labels": {"some": "label"},
        "Driver": "local",
    })
    volumes_response = await docker.volumes.list(filters={"label": "some=label"})
    volumes = volumes_response["Volumes"]
    assert len(volumes) == 1
    volume_data = volumes[0]
    volume = await docker.volumes.get(volume_data["Name"])
    await volume.delete()
    with pytest.raises(DockerError):
        await docker.volumes.get(name)


@pytest.mark.asyncio
@pytest.mark.parametrize("force_delete", [True, False])
async def test_create_show_delete_volume(docker: Docker, force_delete: bool) -> None:
    name = "aiodocker-test-volume"
    volume = await docker.volumes.create({
        "Name": name,
        "Labels": {},
        "Driver": "local",
    })
    assert volume
    data = await volume.show()
    assert data
    await volume.delete(force_delete)
    with pytest.raises(DockerError):
        await docker.volumes.get(name)
