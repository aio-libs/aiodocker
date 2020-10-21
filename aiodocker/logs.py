import warnings
from collections import ChainMap
from typing import TYPE_CHECKING, Any

import aiohttp

from .channel import Channel, ChannelSubscriber


if TYPE_CHECKING:
    from .containers import DockerContainer
    from .docker import Docker


class DockerLog:
    def __init__(self, docker: "Docker", container: "DockerContainer") -> None:
        self.docker = docker
        self.channel = Channel()
        self.container = container
        self.response = None

    def listen(self) -> ChannelSubscriber:
        warnings.warn(
            "use subscribe() method instead", DeprecationWarning, stacklevel=2
        )
        return self.channel.subscribe()

    def subscribe(self) -> ChannelSubscriber:
        return self.channel.subscribe()

    async def run(self, **params: Any) -> None:
        if self.response:
            warnings.warn("already running", RuntimeWarning, stackelevel=2)
            return
        forced_params = {"follow": True}
        default_params = {"stdout": True, "stderr": True}
        params2 = ChainMap(forced_params, params, default_params)
        try:
            self.response = await self.docker._query(
                "containers/{self.container._id}/logs".format(self=self), params=params2
            )
            assert self.response is not None
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
            if self.response is not None:
                try:
                    await self.response.release()
                except Exception:
                    pass
            self.response = None

    async def stop(self) -> None:
        if self.response:
            await self.response.release()
