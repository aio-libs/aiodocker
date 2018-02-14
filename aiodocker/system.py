from typing import Mapping

from .docker import Docker


class DockerSystem(object):
    def __init__(self, docker: Docker) -> None:
        self.docker = docker

    async def info(self) -> Mapping:
        """
        Get system information, similar to `docker info`.

        Returns:
            A dict with docker engine info.
        """

        response = await self.docker._query_json(
            "info",
            method='GET',
        )

        return response
