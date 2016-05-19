import io
import os
import base64
import urllib
import aiohttp
import asyncio
import hashlib
import tarfile
import json
import datetime as dt
import ssl
from aiohttp import websocket

from aiodocker.channel import Channel
from aiodocker.utils import identical


class Docker:
    def __init__(self,
                 url=os.environ.get('DOCKER_HOST', "/run/docker.sock"),
                 ssl_context=None):
        self.url = url
        self.events = DockerEvents(self)
        self.containers = DockerContainers(self)
        if url.startswith('http://'):
            self.connector = aiohttp.TCPConnector()
        elif url.startswith('https://'):
            self.connector = aiohttp.TCPConnector(ssl_context=ssl_context)
        else:
            self.connector = aiohttp.connector.UnixConnector(url)

    @asyncio.coroutine
    def pull(self, image):
        response = yield from self._query(
            "images/create", "POST",
            params={"fromImage": image},
            headers={"content-type": "application/json",},
            stream=True,
        )
        yield from response.release()
        return

    def _endpoint(self, path):
        return "/".join([self.url, path])

    def _query(self, path, method='GET', params=None, timeout=None,
               data=None, headers=None, stream=False, **kwargs):
        url = self._endpoint(path)
        future = asyncio.ensure_future(aiohttp.request(
            method, url,
            connector=self.connector,
            params=params, headers=headers, data=data, **kwargs))

        if timeout:
            response = yield from asyncio.wait_for(future, timeout)
        else:
            response = yield from future

        if (response.status // 100) in [4, 5]:
            what = yield from response.read()
            response.close()
            raise ValueError("Got a failure from the server: '%s'" % (
                what.decode('utf-8').strip()
            ))

        if stream:
            return response

        if 'json' in response.headers.get("Content-Type", ""):
            data = yield from response.json(encoding='utf-8')
            return data

        if 'application/x-tar' in response.headers.get("Content-Type", ""):
            what = yield from response.read()
            return tarfile.open(mode='r', fileobj=io.BytesIO(what))

        try:
            data = yield from response.content.read()  # XXX: Correct?
        except ValueError as e:
            print("Server said", chunk)
            raise

        response.close()
        return data

    def _websocket(self, url, params=None):
        if not params:
            params = {
                'stdout': 1,
                'stderr': 1,
                'stream': 1
            }
        ws = yield from aiohttp.ws_connect(url, connector=self.connector, params=params)
        return ws


class DockerContainers:
    def __init__(self, docker):
        self.docker = docker

    @asyncio.coroutine
    def list(self, **kwargs):
        data = yield from self.docker._query(
            "containers/json",
            method='GET',
            params=kwargs
        )
        return [DockerContainer(self.docker, **x) for x in data]

    @asyncio.coroutine
    def create_or_replace(self, name, config):
        container = None

        try:
            container = yield from self.get(name)
            if not identical(config, container._container):
                running = container._container.get(
                    "State", {}).get("Running", False)
                if running:
                    yield from container.stop()
                yield from container.delete()
                container = None
        except ValueError:
            pass

        if container is None:
            container = yield from self.create(config, name=name)

        return container

    @asyncio.coroutine
    def create(self, config, name=None):
        url = "containers/create"

        config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
        kwargs = {}
        if name:
            kwargs['name'] = name
        data = yield from self.docker._query(
            url,
            method='POST',
            headers={"content-type": "application/json",},
            data=config,
            params=kwargs
        )
        return DockerContainer(self.docker, id=data['Id'])

    @asyncio.coroutine
    def get(self, container, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/json".format(container),
            method='GET',
            params=kwargs
        )
        return DockerContainer(self.docker, **data)


class DockerContainer:
    def __init__(self, docker, **kwargs):
        self.docker = docker
        self._container = kwargs
        self._id = self._container.get("id", self._container.get(
            "ID", self._container.get("Id")))
        self.logs = DockerLog(docker, self)

    @asyncio.coroutine
    def log(self, stdout=False, stderr=False, **kwargs):
        if stdout is False and stderr is False:
            raise TypeError("Need one of stdout or stderr")

        data = yield from self.docker._query(
            "containers/{}/logs".format(self._id),
            method='GET',
            params={
                "stdout": stdout,
                "stderr": stderr,
                "follow": False,
            }
        )
        return data

    @asyncio.coroutine
    def copy(self, resource, **kwargs):
        request = json.dumps({
            "Resource": resource,
        }, sort_keys=True, indent=4).encode('utf-8')
        data = yield from self.docker._query(
            "containers/{}/copy".format(self._id),
            method='POST',
            data=request,
            headers={"content-type": "application/json",},
            params=kwargs
        )
        return data

    @asyncio.coroutine
    def show(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/json".format(self._id),
            method='GET',
            params=kwargs
        )
        self._container = data
        return data

    @asyncio.coroutine
    def stop(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/stop".format(self._id),
            method='POST',
            params=kwargs
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
            params=kwargs
        )
        return data

    @asyncio.coroutine
    def kill(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/kill".format(self._id),
            method='POST',
            params=kwargs
        )
        return data

    @asyncio.coroutine
    def wait(self, timeout=None, **kwargs):
        data = yield from self.docker._query(
            "containers/{}/wait".format(self._id),
            method='POST',
            params=kwargs,
            timeout=timeout,
        )
        return data

    @asyncio.coroutine
    def delete(self, **kwargs):
        data = yield from self.docker._query(
            "containers/{}".format(self._id),
            method='DELETE',
            params=kwargs
        )
        return data

    @asyncio.coroutine
    def websocket(self, params=None):
        url = "containers/{}/attach/ws".format(self._id)
        ws = yield from self.docker._websocket(url, params)
        return ws


class DockerEvents:
    def __init__(self, docker):
        self.running = False
        self.docker = docker
        self.channel = Channel()

    def listen(self):
        return self.channel.listen()

    def saferun(self):
        if self.running:
            return
        self.running = True
        asyncio.async(self.run())

    @asyncio.coroutine
    def run(self):
        self.running = True
        containers = self.docker.containers
        response = yield from self.docker._query(
            'events',
            method='GET',
            stream=True
        )

        while True:
            msg = yield from response.content.readline()
            if not msg:
                break
            data = json.loads(msg.decode('utf-8'))

            if 'time' in data:
                data['time'] = dt.datetime.fromtimestamp(data['time'])

            if 'id' in data and data['status'] in [
                "start", "create",
            ]:
                data['container'] = yield from containers.get(data['id'])

            asyncio.async(self.channel.put(data))
        response.close()
        self.running = False


class DockerLog:
    def __init__(self, docker, container):
        self.docker = docker
        self.channel = Channel()
        self.container = container
        self.running = False

    def listen(self):
        return self.channel.listen()

    def saferun(self):
        if self.running:
            return
        self.running = True
        asyncio.async(self.run())

    @asyncio.coroutine
    def run(self):
        self.running = True
        containers = self.docker.containers
        response = yield from self.docker._query(
            'containers/{id}/logs'.format(id=self.container._id),
            params=dict(
                follow=True,
                stdout=True,
                stderr=True,
            ),
            stream=True,
        )

        for msg in response:
            msg = yield from msg
            asyncio.async(self.channel.put(msg))

        self.running = False
