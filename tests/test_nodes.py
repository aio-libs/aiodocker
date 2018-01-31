import aiohttp
import asyncio
import pytest
from distutils.version import StrictVersion



@pytest.mark.asyncio
async def test_nodes_list(swarm):
    swarm_nodes = await swarm.nodes.list()
    assert len(swarm_nodes) == 1

@pytest.mark.asyncio
async def test_node_inspect(swarm):
    swarm_nodes = await swarm.nodes.list()
    node_id, hostname = swarm_nodes[0]["ID"], swarm_nodes[0]["Description"]["Hostname"]
    print(node_id)
    print(hostname)
    node = await swarm.nodes.inspect(hostname)
    print(node)
    assert node_id in node['ID']
