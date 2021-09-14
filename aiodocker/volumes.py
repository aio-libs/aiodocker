import json

from .utils import clean_filters


class DockerVolumes:
    def __init__(self, docker):
        self.docker = docker

    async def list(self, *, filters=None):
        params = {} if filters is None else {"filters": clean_filters(filters)}

        data = await self.docker._query_json("volumes", params=params)
        return data

    async def get(self, id):
        data = await self.docker._query_json(
            "networks/{id}".format(id=id), method="GET"
        )
        return DockerVolume(self.docker, data["Name"])

    async def create(self, config):
        config = json.dumps(config, sort_keys=True).encode("utf-8")
        data = await self.docker._query_json(
            "volumes/create", method="POST", data=config
        )
        return DockerVolume(self.docker, data["Name"])


class DockerVolume:
    def __init__(self, docker, name):
        self.docker = docker
        self.name = name

    async def show(self):
        data = await self.docker._query_json("volumes/{self.name}".format(self=self))
        return data

    async def delete(self):
        async with self.docker._query(
            "volumes/{self.name}".format(self=self), method="DELETE"
        ):
            pass
