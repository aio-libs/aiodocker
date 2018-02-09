from typing import Dict, Any


class DockerSwarmNodes(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self) -> Dict[str, Any]:
        """
        Inspect a swarm

        Returns:
            Info about the swarm
        """
        # TODO add filters

        response = await self.docker._query_json(
            "nodes",
            method='GET',
        )

        return response

    async def inspect(self, *, node_id: str) -> Dict[str, Any]:
        """
        Inspect a node

        Args:
            node_id: The ID or name of the node

        Returns:
            a dict with info about the node
        """

        response = await self.docker._query_json(
            "nodes/{node_id}".format(node_id=node_id),
            method="GET",
        )
        return response

    async def update(
        self, *, node_id: str, version: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inspect a node

        Args:
            node_id: The ID or name of the node

        Returns:
            a dict with info about the node
        """

        params = {"version": version}

        if "Role" in data:
            assert data['Role'] in {"worker", "manager"}

        if "Availability" in data:
            assert data['Availability'] in {"active", "pause", "drain"}

        response = await self.docker._query_json(
            "nodes/{node_id}/update".format(node_id=node_id),
            method="POST",
            params=params,
            data=data
        )
        return response

    async def remove(
        self,
        *,
        node_id: str,
        force: bool=False
    ) -> Dict[str, Any]:
        """
        Inspect a node

        Args:
            node_id: The ID or name of the node

        Returns:
            a dict with info about the node
        """

        params = {"force": force}

        response = await self.docker._query_json(
            "nodes/{node_id}".format(node_id=node_id),
            method="DELETE",
            params=params,
        )
        return response
