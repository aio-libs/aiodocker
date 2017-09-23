import json
from typing import Optional, Dict


class DockerSwarm(object):
    def __init__(self, docker):
        self.docker = docker

    async def init(self,
                   *,
                   advertise_addr: Optional[str]=None,
                   listen_addr: str="0.0.0.0:2377",
                   force_new_cluster: bool=False,
                   swarm_spec: Optional[Dict]=None
                   ) -> str:
        """
        Initialize a new swarm

        Args:
            ListenAddr: listen address used for inter-manager communication
            AdvertiseAddr: address advertised to other nodes.
            ForceNewCluster: Force creation of a new swarm.
            SwarmSpec: User modifiable swarm configuration.

        Returns:
            id of the swarm node
        """

        data = {
            'AdvertiseAddr': advertise_addr,
            'ListenAddr': listen_addr,
            'ForceNewCluster': force_new_cluster,
            'Spec': swarm_spec,
        }

        data_str = json.dumps(data)

        response = await self.docker._query(
            "swarm/init",
            method='POST',
            headers={"content-type": "application/json", },
            data=data_str
        )

        return response

    async def inspect(self) -> Dict:
        """
        Inspect a swarm

        Returns:
            Info about the swarm
        """

        response = await self.docker._query_json(
            "swarm",
            method='GET',
        )

        return response

    async def leave(self, *, force: bool=False) -> bool:
        """
        Leave a swarm

        Args:
            force: force to leave the swarm even if the node is a master

        """

        params = {"force": force}

        await self.docker._query(
            "swarm/leave",
            method='POST',
            params=params
        )

        return True
