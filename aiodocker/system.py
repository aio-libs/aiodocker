from __future__ import annotations

from collections.abc import Mapping, Sequence

from yarl import URL


class DockerSystem:
    def __init__(self, docker) -> None:
        self.docker = docker

    async def info(self) -> Mapping:
        """
        Get system information, similar to `docker info`.

        Returns:
            A dict with docker engine info.
        """

        response = await self.docker._query_json("info", method="GET")

        return response

    async def df(self, *, types: Sequence[str] | None = None) -> Mapping:
        """
        Get data usage information, similar to `docker system df`.

        Args:
            types: Object types to compute usage for (``image``,
                ``container``, ``volume``, ``build-cache``). Requires API
                v1.42+; earlier versions ignore it and compute all types.

        Returns:
            A dict with disk usage per object type.
        """

        url = URL("system/df")
        if types:
            url = url.with_query([("type", object_type) for object_type in types])
        response = await self.docker._query_json(url, method="GET")

        return response
