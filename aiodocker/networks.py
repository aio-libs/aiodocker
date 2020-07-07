import json
from typing import Any, Dict, List


class DockerNetworks:
    def __init__(self, docker):
        self.docker = docker

    async def list(self) -> List[Dict[str, Any]]:
        data = await self.docker._query_json("networks")
        return data

    async def create(self, config: Dict[str, Any]) -> "DockerNetwork":
        bconfig = json.dumps(config, sort_keys=True).encode("utf-8")
        data = await self.docker._query_json(
            "networks/create", method="POST", data=bconfig
        )
        return DockerNetwork(self.docker, data["Id"])

    async def get(self, net_specs: str) -> "DockerNetwork":
        data = await self.docker._query_json(
            "networks/{net_specs}".format(net_specs=net_specs), method="GET"
        )
        return DockerNetwork(self.docker, data["Id"])


class DockerNetwork:
    def __init__(self, docker, id_):
        self.docker = docker
        self.id = id_

    async def show(self) -> Dict[str, Any]:
        data = await self.docker._query_json("networks/{self.id}".format(self=self))
        return data

    async def delete(self) -> bool:
        async with self.docker._query(
            "networks/{self.id}".format(self=self), method="DELETE"
        ) as resp:
            return resp.status == 204

    async def connect(self, config: Dict[str, Any]) -> None:
        bconfig = json.dumps(config, sort_keys=True).encode("utf-8")
        await self.docker._query_json(
            "networks/{self.id}/connect".format(self=self), method="POST", data=bconfig
        )

    async def disconnect(self, config: Dict[str, Any]) -> None:
        bconfig = json.dumps(config, sort_keys=True).encode("utf-8")
        await self.docker._query_json(
            "networks/{self.id}/disconnect".format(self=self),
            method="POST",
            data=bconfig,
        )
