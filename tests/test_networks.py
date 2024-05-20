import pytest

import aiodocker


@pytest.mark.asyncio
async def test_list_networks(docker):
    data = await docker.networks.list()
    networks = {net["Name"]: net for net in data}
    assert "none" in networks
    assert networks["none"]["Driver"] == "null"


@pytest.mark.asyncio
async def test_list_networks_with_filter(docker):
    await docker.networks.create({
        "Name": "test-net-filter",
        "Labels": {"some": "label"},
    })
    networks = await docker.networks.list(filters={"label": "some=label"})
    assert len(networks) == 1


@pytest.mark.asyncio
async def test_networks(docker):
    network = await docker.networks.create({"Name": "test-net"})
    net_find = await docker.networks.get("test-net")
    assert (await net_find.show())["Name"] == "test-net"
    assert isinstance(network, aiodocker.networks.DockerNetwork)
    data = await network.show()
    assert data["Name"] == "test-net"
    container = None
    try:
        container = await docker.containers.create({"Image": "python"}, name="test-net")
        await network.connect({"Container": "test-net"})
        await network.disconnect({"Container": "test-net"})
    finally:
        if container is not None:
            await container.delete()
        network_delete_result = await network.delete()
        assert network_delete_result is True


@pytest.mark.asyncio
async def test_network_delete_error(docker):
    network = await docker.networks.create({"Name": "test-delete-net"})
    assert await network.delete() is True
    with pytest.raises(aiodocker.exceptions.DockerError):
        await network.delete()
