import pytest


@pytest.mark.asyncio
async def test_create_show_delete_volume(docker):
    name = "aiodocker-test-volume"
    volume = await docker.volumes.create(
        {"Name": name, "Labels": {}, "Driver": "local"}
    )
    assert volume
    data = await volume.show()
    assert data
    await volume.delete()
