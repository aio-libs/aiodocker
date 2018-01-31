import json
from typing import Optional, Dict, Any


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

    async def inspect(self, node_id: str) -> Dict[str, Any]:
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
