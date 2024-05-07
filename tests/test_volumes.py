import pytest


@pytest.mark.asyncio
async def test_create_search_get_delete(docker):
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


@pytest.mark.asyncio
async def test_create_show_delete_volume(docker):
    name = "aiodocker-test-volume"
    volume = await docker.volumes.create({
        "Name": name,
        "Labels": {},
        "Driver": "local",
    })
    assert volume
    data = await volume.show()
    assert data
    await volume.delete()
