

class DockerSystemAPI(object):
    def __init__(self, api_client):
        self.api_client = api_client

    async def info(self):
        """
        Display system-wide information. Identical to the ``docker info``
        command.

        Returns:
            (dict): The info as a dict

        Raises:
            :py:class:`aiodocker.errors.APIError`
                If the server returns an error.
        """
        data = await self.api_client._query_json("info")
        return data
