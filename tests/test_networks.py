import pytest
import aiodocker


@pytest.mark.asyncio
async def test_list_networks(docker):
    data = await docker.networks.list()
    networks = {net['Name']: net for net in data}
    assert 'none' in networks
    assert networks['none']['Driver'] == 'null'


@pytest.mark.asyncio
async def test_create_and_destroy_network(docker):
    network = await docker.networks.create({'Name': 'test-net'})
    assert isinstance(network, aiodocker.networks.DockerNetwork)
    data = await network.show()
    assert data['Name'] == 'test-net'
    await network.delete()
