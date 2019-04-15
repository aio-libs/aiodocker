class Exec:
    def __init__(self, exec_id, container):
        self.exec_id = exec_id
        self.container = container

    @classmethod
    async def create(cls, container, **kwargs):
        data = await container.docker._query_json(
            "containers/{container._id}/exec".format(container=container),
            method='POST', params=kwargs,
        )
        return cls(data["Id"], container)

    async def start(self, **kwargs):
        # Don't use docker._query_json
        # content-type of response will be "vnd.docker.raw-stream", so it will cause error.
        response = await self.container.docker._query(
            "exec/{exec_id}/start".format(exec_id=self.exec_id),
            method='POST',
            headers={"content-type": "application/json"},
            data=json.dumps(kwargs),
        )
        result = await response.read()
        await response.release()
        return result

    async def resize(self, **kwargs):
        data = await self.container.docker._query_json(
            "exec/{exec_id}/resize".format(self=self.exec_id), method='POST',
            params=kwargs,
        )
        return data

    async def inspect(self):
        data = await self.container.docker._query_json(
            "exec/{exec_id}/json".format(self=self.exec_id), method='GET',
        )
        return data
