import json
from typing import Optional, Dict, List

from .utils import clean_map


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
        Initialize a new swarm.

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
        Inspect a swarm.

        Returns:
            Info about the swarm
        """

        response = await self.docker._query_json(
            "swarm",
            method='GET',
        )

        return response

    async def join(
        self,
        *,
        remote_addrs: List[str],
        join_token: str,
        listen_addr: str='0.0.0.0:2377',
        advertise_addr: str=None,
        data_path_addr: str=None,
        ) -> bool:
        """
        Join a swarm.

        Args:
            listen_addr: Listen address used for inter-manager communication
            advertise_addr: Externally reachable address advertised to other nodes. If AdvertiseAddr is not specified, it will be automatically detected when possible.
            data_path_addr: Address or interface to use for data path traffic, if data_path_addr is unspecified, the same address as AdvertiseAddr is used.
            remote_addrs: Addresses of manager nodes already participating in the swarm.
            join_token: Secret token for joining this swarm.
        """

        data = {
            "RemoteAddrs": remote_addrs,
            "JoinToken": join_token,
            "ListenAddr": listen_addr,
            "AdvertiseAddr": advertise_addr,
            "DataPathAddr": data_path_addr,
        }

        await self.docker._query(
            "swarm/join",
            method='POST',
            data=json.dumps(clean_map(data))
        )

        return True

    async def leave(self, *, force: bool=False) -> bool:
        """
        Leave a swarm.

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
