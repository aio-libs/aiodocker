import aiohttp
import asyncio
import pytest


@pytest.mark.asyncio
async def test_nodes_list(swarm):
    swarm_nodes = await swarm.nodes.list()
    assert len(swarm_nodes) == 1

@pytest.mark.asyncio
async def test_node_inspect(swarm):
    swarm_nodes = await swarm.nodes.list()
    node_id, hostname = swarm_nodes[0]["ID"], swarm_nodes[0]["Description"]["Hostname"]

    node = await swarm.nodes.inspect(hostname)
    assert node_id in node['ID']

    node = await swarm.nodes.inspect(node_id)
    assert hostname in node["Description"]["Hostname"]

@pytest.mark.asyncio
async def test_node_remove(swarm):
    swarm_nodes = await swarm.nodes.list()
    node_id, hostname = swarm_nodes[0]["ID"], swarm_nodes[0]["Description"]["Hostname"]
    print(node_id)
    print(hostname)
    node = await swarm.nodes.remove(hostname)
    print(node)
    assert node_id in node['ID']

@pytest.mark.asyncio
async def test_node_update(swarm):
    swarm_nodes = await swarm.nodes.list()
    print(swarm_nodes)
    node_id, version = swarm_nodes[0]["ID"], swarm_nodes[0]["Version"]["Index"]
    data = {
        "Availability": "active",
        "Role": "manager",
        'Labels': {
            "new_label": "true"
        }
    }
    await swarm.nodes.update(node_id, version, data)

    node = await swarm.nodes.inspect(node_id)
    assert node['Spec']['Labels']["new_label"] == "true"
