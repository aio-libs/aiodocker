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
        return DockerEvents(self)

    def containers(self):
        return DockerContainers(self)


class DockerContainers:
    def __init__(self, docker):
        self.docker = docker

    @asyncio.coroutine
    def list(self, **kwargs):
        data = yield from self.docker._query(
            "containers/json",
            method='GET',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def show(self, container, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/json".format(container),
            method='GET',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def stop(self, container, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/stop".format(container),
            method='POST',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def kill(self, container, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/kill".format(container),
            method='POST',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def delete(self, container, **kwargs):
        data = yield from self.docker._query(
            "containers/{}".format(container),
            method='DELETE',
            **kwargs
        )
        return data



class DockerEvents:
    def __init__(self, docker):
        self.docker = docker
        self.channel = Channel()

    def listen(self):
        return self.channel.listen()

    @asyncio.coroutine
    def run(self):
        containers = self.docker.containers()
        response = yield from aiohttp.request(
            'GET',
            self.docker._endpoint('events')
        )

        while True:
            try:
                chunk = yield from response.content.read()  # XXX: Correct?
                data = json.loads(chunk.decode('utf-8'))
                if 'time' in data:
                    data['time'] = dt.datetime.fromtimestamp(data['time'])

                if 'id' in data:
                    data['container'] = yield from containers.show(data['id'])

                asyncio.async(self.channel.put(data))
            except aiohttp.EofStream:
                break
        response.close()
