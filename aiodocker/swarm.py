from typing import Dict, List

from .utils import clean_map


class DockerSwarm(object):
    def __init__(self, docker):
        self.docker = docker

    async def init(
        self,
        *,
        advertise_addr: str=None,
        listen_addr: str="0.0.0.0:2377",
        force_new_cluster: bool=False,
        swarm_spec: Dict=None
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

        response = await self.docker._query_json(
            "swarm/init",
            method='POST',
            data=data
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
            listen_addr
                Used for inter-manager communication

            advertise_addr
                Externally reachable address advertised to other nodes.

            data_path_addr
                Address or interface to use for data path traffic.

            remote_addrs
                Addresses of manager nodes already participating in the swarm.

            join_token
                Secret token for joining this swarm.
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
            data=clean_map(data)
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
