from .api.client import APIClient
from .models.containers import ContainerCollection
from .models.images import ImageCollection


class DockerClient(object):
    def __init__(self, *args, **kwargs):
        self.api = APIClient(*args, **kwargs)

    @property
    def containers(self):
        """
        An object for managing containers on the server. See the
        :doc:`containers documentation <containers>` for full details.
        """
        return ContainerCollection(client=self)

    @property
    def images(self):
        """
        An object for managing images on the server. See the
        :doc:`images documentation <images>` for full details.
        """
        return ImageCollection(client=self)

    async def close(self):
        await self.api.close()

    async def version(self):
        return await self.api.version()
    version.__doc__ = APIClient.version.__doc__

    async def info(self):
        """
        Display system-wide information. Identical to the ``docker info``
        command.

        Returns:
            (dict): The info as a dict

        Raises:
            :py:class:`docker.errors.APIError`
                If the server returns an error.
        """
        return await self.api.system.info()
