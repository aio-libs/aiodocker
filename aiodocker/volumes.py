import json

from .utils import clean_filters


class DockerVolumes:
    def __init__(self, docker):
        self.docker = docker

    async def list(self, *, filters=None):
        """
        Return a list of volumes

        Args:
            filters: a dict with a list of filters

        Available filters:
            dangling=<boolean>
            driver=<volume-driver-name>
            label=<key> or label=<key>:<value>
            name=<volume-name>
        """
        params = {} if filters is None else {"filters": clean_filters(filters)}

        data = await self.docker._query_json("volumes", params=params)
        return data

    async def get(self, id):
        data = await self.docker._query_json(f"volumes/{id}", method="GET")
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
        data = await self.docker._query_json(f"volumes/{self.name}")
        return data

    async def delete(self):
        async with self.docker._query(f"volumes/{self.name}", method="DELETE"):
            pass
