import pytest

from aiodocker.exceptions import DockerError


@pytest.mark.asyncio
async def test_swarm_inspect(swarm):
    swarm_info = await swarm.swarm.inspect()
    assert "ID" in swarm_info
    assert "Spec" in swarm_info


@pytest.mark.asyncio
async def test_swarm_failing_joining(swarm):
    swarm_info = await swarm.swarm.inspect()
    system_info = await swarm.system.info()
    swarm_addr = [system_info["Swarm"]["RemoteManagers"][-1]["Addr"]]
    token = swarm_info["JoinTokens"]["Worker"]
    with pytest.raises(DockerError):
        await swarm.swarm.join(join_token=token, remote_addrs=swarm_addr)
