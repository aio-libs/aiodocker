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
        )
        yield from response.release()
        return

    def _endpoint(self, path):
        return "/".join([self.url, path])

    def _query(self, path, method='GET', params=None, timeout=None,
               data=None, headers=None, **kwargs):
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

        return response

    def _result(self, response, response_type=None):
        if not response_type:
            ct = response.headers.get("Content-Type", "")
            if 'json' in ct:
                response_type = 'json'
            elif 'x-tar' in ct:
                response_tye = 'tar'
            else:
                raise TypeError("Unrecognized response type: {}".format(ct))
        if 'tar' == response_type:
            what = yield from response.read()
            return tarfile.open(mode='r', fileobj=io.BytesIO(what))

        if 'json' == response_type:
            data = yield from response.json(encoding='utf-8')
        elif 'text' ==  response_type:
            data = yield from response.text(encoding='utf-8')
        else:
            data = yield from response.read()

        response.release()
        return data

    def _websocket(self, url, **params):
        if not params:
            params = {
                'stdout': 1,
                'stderr': 1,
                'stream': 1
            }
        url = self._endpoint(url) + "?" + urllib.parse.urlencode(params)
        ws = yield from aiohttp.ws_connect(url, connector=self.connector)
        return ws

    def _query_json(self, *args, **kwargs):
        response = yield from self._query(*args, **kwargs)
        data = yield from self._result(response, 'json')
        return data


class DockerContainers(object):
    def __init__(self, docker):
        self.docker = docker

    @asyncio.coroutine
    def list(self, **kwargs):
        data = yield from self.docker._query_json(
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
        data = yield from self.docker._query_json(
            url,
            method='POST',
            headers={"content-type": "application/json",},
            data=config,
            params=kwargs
        )
        return DockerContainer(self.docker, id=data['Id'])

    @asyncio.coroutine
    def get(self, container, **kwargs):
        data = yield from self.docker._query_json(
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
    def log(self, stdout=False, stderr=False, follow=False, **kwargs):
        if stdout is False and stderr is False:
            raise TypeError("Need one of stdout or stderr")

        params = {
            "stdout": stdout,
            "stderr": stderr,
            "follow": follow,
        }
        params.update(kwargs)

        response = yield from self.docker._query(
            "containers/{}/logs".format(self._id),
            method='GET',
            params=params,
        )
        if follow:
            return response.content
        data = yield from response.text()
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
        data = yield from self.docker._query_json(
            "containers/{}/json".format(self._id),
            method='GET',
            params=kwargs
        )
        self._container = data
        return data

    @asyncio.coroutine
    def stop(self, **kwargs):
        response = yield from self.docker._query(
            "containers/{}/stop".format(self._id),
            method='POST',
            params=kwargs
        )
        yield from response.release()
        return

    @asyncio.coroutine
    def start(self, config, **kwargs):
        config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
        response = yield from self.docker._query(
            "containers/{}/start".format(self._id),
            method='POST',
            headers={"content-type": "application/json",},
            data=config,
            params=kwargs
        )
        yield from response.release()
        return

    @asyncio.coroutine
    def kill(self, **kwargs):
        data = yield from self.docker._query_json(
            "containers/{}/kill".format(self._id),
            method='POST',
            params=kwargs
        )
        return data

    @asyncio.coroutine
    def wait(self, timeout=None, **kwargs):
        data = yield from self.docker._query_json(
            "containers/{}/wait".format(self._id),
            method='POST',
            params=kwargs,
            timeout=timeout,
        )
        return data

    @asyncio.coroutine
    def delete(self, **kwargs):
        response = yield from self.docker._query(
            "containers/{}".format(self._id),
            method='DELETE',
            params=kwargs
        )
        yield from response.release()
        return

    @asyncio.coroutine
    def websocket(self, **params):
        url = "containers/{}/attach/ws".format(self._id)
        ws = yield from self.docker._websocket(url, **params)
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
            method='GET'
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
            )
        )

        for msg in response:
            msg = yield from msg
            asyncio.async(self.channel.put(msg))

        self.running = False
