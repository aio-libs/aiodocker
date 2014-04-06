import urllib
import aiohttp
import asyncio
import json
import datetime as dt
from aiodocker.channel import Channel


class Docker:
    def __init__(self, url):
        self.url = url
        self.events = DockerEvents(self)
        self.containers = DockerContainers(self)

    def _endpoint(self, path, **kwargs):
        string = "/".join([self.url, path])
        if kwargs:
            string += "?" + urllib.parse.urlencode(kwargs)
        return string

    def _query(self, path, method='GET', data=None, headers=None, **kwargs):
        url = self._endpoint(path, **kwargs)
        response = yield from aiohttp.request(
                method, url, headers=headers, data=data)
        # if response.status not in [200]:
        #     raise ValueError("Got a failure from the server")

        data = None
        try:
            chunk = yield from response.content.read()  # XXX: Correct?
            data = json.loads(chunk.decode('utf-8'))
        except aiohttp.EofStream:
            pass
        response.close()
        return data


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
        return [DockerContainer(self.docker **x) for x in data]

    @asyncio.coroutine
    def create(self, config, name=None):
        url = "containers/create"

        config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
        data = yield from self.docker._query(
            url,
            method='POST',
            headers={"content-type": "application/json",},
            data=config,
            name=name
        )
        return DockerContainer(self.docker, id=data['Id'])

    @asyncio.coroutine
    def run(self, config, name=None):
        x = yield from self.create(config, name=name)
        yield from x.start({
             "Binds":[],
             "LxcConf":{"lxc.utsname":"docker"},
             "PortBindings":{},
             "PublishAllPorts":False,
             "Privileged":False
        })
        return x

    @asyncio.coroutine
    def get(self, container, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/json".format(container),
            method='GET',
            **kwargs
        )
        return DockerContainer(self.docker, **data)


class DockerContainer:
    def __init__(self, docker, **kwargs):
        self.docker = docker
        self._container = kwargs
        self._id = self._container.get("id", self._container.get("ID"))

    @asyncio.coroutine
    def show(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/json".format(self._id),
            method='GET',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def stop(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/stop".format(self._id),
            method='POST',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def start(self, config, **kwargs):
        config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
        data = yield from self.docker._query(
            "containers/{}/start".format(self._id),
            method='POST',
            headers={"content-type": "application/json",},
            data=config,
            **kwargs
        )
        return data

    @asyncio.coroutine
    def kill(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/kill".format(self._id),
            method='POST',
            **kwargs
        )
        return data

    @asyncio.coroutine
    def delete(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}".format(self.container['id']),
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
        containers = self.docker.containers
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
                    data['container'] = yield from containers.get(data['id'])

                asyncio.async(self.channel.put(data))
            except aiohttp.EofStream:
                break
        response.close()
