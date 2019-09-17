import warnings
from collections import ChainMap

import aiohttp

from .channel import Channel


class DockerLog:
    def __init__(self, docker, container):
        self.docker = docker
        self.channel = Channel()
        self.container = container
        self.response = None

    def listen(self):
        warnings.warn(
            "use subscribe() method instead", DeprecationWarning, stacklevel=2
        )
        return self.channel.subscribe()

    def subscribe(self):
        return self.channel.subscribe()

    async def run(self, **params):
        if self.response:
            warnings.warn("already running", RuntimeWarning, stackelevel=2)
            return
        forced_params = {"follow": True}
        default_params = {"stdout": True, "stderr": True}
        params = ChainMap(forced_params, params, default_params)
        try:
            self.response = await self.docker._query(
                "containers/{self.container._id}/logs".format(self=self), params=params
            )
            while True:
                msg = await self.response.content.readline()
                if not msg:
                    break
                await self.channel.publish(msg)
        except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError):
            pass
        finally:
            # signal termination to subscribers
            await self.channel.publish(None)
            try:
                await self.response.release()
            except Exception:
                pass
            self.response = None

    async def stop(self):
        if self.response:
            await self.response.release()
