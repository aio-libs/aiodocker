import json


class DockerNetworks:
    def __init__(self, docker):
        self.docker = docker

    async def list(self):
        data = await self.docker._query_json("networks")
        return data

    async def create(self, config):
        config = json.dumps(config, sort_keys=True).encode('utf-8')
        data = await self.docker._query_json(
            "networks/create",
            method="POST",
            data=config,
        )
        return DockerNetwork(self.docker, data['Id'])


class DockerNetwork:
    def __init__(self, docker, id_):
        self.docker = docker
        self.id = id_

    async def show(self):
        data = await self.docker._query_json(
            "networks/{self.id}".format(self=self)
        )
        return data

    async def delete(self):
        response = await self.docker._query(
            "networks/{self.id}".format(self=self),
            method="DELETE",
        )
        await response.release()
        return

    async def connect(self, config):
        config = json.dumps(config, sort_keys=True).encode('utf-8')
        await self.docker._query_json(
            "networks/{self.id}/connect".format(self=self),
            method="POST",
            data=config,
        )

    async def disconnect(self, config):
        config = json.dumps(config, sort_keys=True).encode('utf-8')
        await self.docker._query_json(
            "networks/{self.id}/disconnect".format(self=self),
            method="POST",
            data=config,
        )
