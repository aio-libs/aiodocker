import urllib
import aiohttp
import asyncio
import json
import datetime as dt
from aiodocker.channel import Channel


class Docker:
    def __init__(self, url):
        self.url = url

    def _endpoint(self, path, **kwargs):
        string = "/".join([self.url, path])
        if kwargs:
            string += "?" + urllib.parse.urlencode(kwargs)
        return string

    def _query(self, path, method='GET', data=None, **kwargs):
        url = self._endpoint(path, **kwargs)
        response = yield from aiohttp.request(method, url, data=data)
        data = None
        try:
            chunk = yield from response.content.read()  # XXX: Correct?
            data = json.loads(chunk.decode('utf-8'))
        except aiohttp.EofStream:
            pass
        response.close()
        return data

    def events(self):
        e = DockerEvents(self)
        return e


class DockerEvents:
    def __init__(self, docker):
        self.docker = docker
        self.channel = Channel()

    def listen(self):
        return self.channel.listen()

    @asyncio.coroutine
    def run(self):
        response = yield from aiohttp.request(
            'GET', self.docker._endpoint('events'))

        while True:
            try:
                chunk = yield from response.content.read()  # XXX: Correct?
                data = json.loads(chunk.decode('utf-8'))
                if 'time' in data:
                    data['time'] = dt.datetime.fromtimestamp(data['time'])

                asyncio.async(self.channel.put(data))
            except aiohttp.EofStream:
                break
        response.close()
