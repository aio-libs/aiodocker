import pytest
import aiodocker


@pytest.mark.asyncio
async def test_list_networks(docker):
    data = await docker.networks.list()
    networks = {net['Name']: net for net in data}
    assert 'none' in networks
    assert networks['none']['Driver'] == 'null'


@pytest.mark.asyncio
async def test_networks(docker):
    network = await docker.networks.create({'Name': 'test-net'})
    assert isinstance(network, aiodocker.networks.DockerNetwork)
    data = await network.show()
    assert data['Name'] == 'test-net'
    container = None
    try:
        container = await docker.containers.create(
            {'Image': 'alpine'},
            name='test-net'
        )
        await network.connect({'Container': 'test-net'})
        await network.disconnect({'Container': 'test-net'})
    finally:
        if container is not None:
            await container.delete()
        await network.delete()
