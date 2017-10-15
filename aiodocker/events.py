import asyncio
from collections import ChainMap
import datetime as dt
import warnings

from .channel import Channel
from .jsonstream import json_stream_result
from .utils import human_bool


class DockerEvents:
    def __init__(self, docker):
        self.docker = docker
        self.channel = Channel()
        self.json_stream = None
        self.task = None

    def listen(self):
        warnings.warn("use subscribe() method instead",
                      DeprecationWarning, stacklevel=2)
        return self.channel.subscribe()

    def subscribe(self, *, create_task=True):
        """Subscribes to the Docker events channel. Use the keyword argument
        create_task=False to prevent automatically spawning the background
        tasks that listen to the events.

        This function returns a ChannelSubscriber object.
        """
        if create_task and not self.task:
            self.task = asyncio.ensure_future(self.run())
        return self.channel.subscribe()

    def _transform_event(self, data):
        if 'time' in data:
            data['time'] = dt.datetime.fromtimestamp(data['time'])
        return data

    async def run(self, **params):
        """
        Query the events endpoint of the Docker daemon.

        Publish messages inside the asyncio queue.
        """
        if self.json_stream:
            warnings.warn("already running",
                          RuntimeWarning, stackelevel=2)
            return
        forced_params = {
            'stream': True,
        }
        params = ChainMap(forced_params, params)
        try:
            # timeout has to be set to 0, None is not passed
            # Otherwise after 5 minutes the client
            # will close the connection
            # http://aiohttp.readthedocs.io/en/stable/client_reference.html#aiohttp.ClientSession.request
            response = await self.docker._query(
                "events",
                method="GET",
                params=params,
                timeout=0
            )
            self.json_stream = await json_stream_result(
                response,
                self._transform_event,
                human_bool(params['stream']),
            )
            try:
                async for data in self.json_stream:
                    await self.channel.publish(data)
            finally:
                if self.json_stream is not None:
                    await self.json_stream._close()
                self.json_stream = None
        finally:
            # signal termination to subscribers
            await self.channel.publish(None)

    async def stop(self):
        if self.json_stream is not None:
            await self.json_stream._close()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
