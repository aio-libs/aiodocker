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

from .channel import Channel
from .utils import identical
from .multiplexed import MultiplexedResult
from .jsonstream import JsonStreamResult


class Docker:
    def __init__(self,
                 url=os.environ.get('DOCKER_HOST', "/run/docker.sock"),
                 connector=None,
                 session=None,
                 ssl_context=None):
        self.url = url
        self.events = DockerEvents(self)
        self.containers = DockerContainers(self)
        self.images = DockerImages(self)
        if connector is None:
            if url.startswith('http://'):
                connector = aiohttp.TCPConnector()
            elif url.startswith('https://'):
                connector = aiohttp.TCPConnector(ssl_context=ssl_context)
            elif url.startswith('unix://'):
                connector = aiohttp.connector.UnixConnector(url[8:])
                self.url = "http://docker" #aiohttp treats this as a proxy
            elif url.startswith('/'):
                connector = aiohttp.connector.UnixConnector(url)
                self.url = "http://docker" #aiohttp treats this as a proxy
            else:
                connector = aiohttp.connector.UnixConnector(url)
        self.connector = connector
        if session is None:
            session = aiohttp.ClientSession(connector=self.connector)
        self.session = session

    @asyncio.coroutine
    def auth(self, **credentials):
        response = yield from self._query_json(
            "auth", "POST",
            data=credentials,
            headers={"content-type": "application/json",},
        )
        return response

    @asyncio.coroutine
    def pull(self, image, stream=False):
        response = yield from self._query(
            "images/create", "POST",
            params={"fromImage": image},
            headers={"content-type": "application/json",},
        )
        json_stream = yield from self._json_stream_result(response, stream=stream)
        return json_stream

    def _endpoint(self, path):
        return "/".join([self.url, path])

    @asyncio.coroutine
    def _query(self, path, method='GET', params=None, timeout=None,
               data=None, headers=None, **kwargs):
        url = self._endpoint(path)
        future = asyncio.ensure_future(self.session.request(
            method, url,
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

    @asyncio.coroutine
    def _result(self, response, response_type=None):
        if not response_type:
            ct = response.headers.get("Content-Type", "")
            if 'json' in ct:
                response_type = 'json'
            elif 'x-tar' in ct:
                response_type = 'tar'
            elif 'text/plain' in ct:
                response_type = 'text'
            else:
                raise TypeError("Unrecognized response type: {}".format(ct))
        if 'tar' == response_type:
            what = yield from response.read()
            yield from response.release()
            return tarfile.open(mode='r', fileobj=io.BytesIO(what))

        if 'json' == response_type:
            data = yield from response.json(encoding='utf-8')
        elif 'text' ==  response_type:
            data = yield from response.text(encoding='utf-8')
        else:
            data = yield from response.read()

        yield from response.release()
        return data

    def _json_stream_result(self, response, transform=None, stream=True):
        json_stream = JsonStreamResult(response, transform)
        if stream:
            return json_stream
        data = []
        i = yield from json_stream.__aiter__()
        while True:
            try:
                line = yield from i.__anext__()
            except StopAsyncIteration:
                break
            else:
                data.append(line)

        return data

    def _multiplexed_result(self, response):
        return MultiplexedResult(response)

    @asyncio.coroutine
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

    @asyncio.coroutine
    def _query_json(self, *args, **kwargs):
        response = yield from self._query(*args, **kwargs)
        data = yield from self._result(response, 'json')
        return data


class DockerImages(object):
    def __init__(self, docker):
        self.docker = docker

    @asyncio.coroutine
    def list(self, **params):
        response = yield from self.docker._query_json(
            "images/json", "GET",
            params=params,
            headers={"content-type": "application/json",},
        )
        return response

    @asyncio.coroutine
    def get(self, name):
        response = yield from self.docker._query_json(
            "images/{0}/json".format(name),
            headers={"content-type": "application/json",},
        )
        return response

    @asyncio.coroutine
    def history(self, name):
        response = yield from self.docker._query_json(
            "images/{0}/history".format(name),
            headers={"content-type": "application/json",},
        )
        return response

    @asyncio.coroutine
    def push(self, name, tag=None, auth=None, stream=False):
        headers = {
            "content-type": "application/json",
            "X-Registry-Auth": "FOO",
        }
        params = {}
        if auth:
            if isinstance(auth, dict):
                auth = json.dumps(auth).encode('ascii')
                auth = base64.b64encode(auth)
            if not isinstance(auth, (bytes, str)):
                raise TypeError("auth must be base64 encoded string/bytes or a dictionary")
            if isinstance(auth, bytes):
                auth = auth.decode('ascii')
            headers['X-Registry-Auth'] = auth
        if tag:
            params['tag'] = tag
        response = yield from self.docker._query(
            "images/{0}/push".format(name),
            "POST",
            params=params,
            headers=headers,
        )
        json_stream = yield from self.docker._json_stream_result(response, stream=stream)
        return json_stream

    @asyncio.coroutine
    def tag(self, name, tag=None, repo=None):
        params = {}
        if tag:
            params['tag'] = tag
        if repo:
            params['repo'] = repo
        response = yield from self.docker._query_json(
            "images/{0}/tag".format(name),
            "POST",
            params=params,
            headers={"content-type": "application/json"},
        )
        return response

    @asyncio.coroutine
    def delete(self, name, **params):
        response = yield from self.docker._query_json(
            "images/{0}/tag".format(name),
            "DELETE",
            params=params,
            headers={"content-type": "application/json",},
        )
        return response


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

    def container(self, container_id, **kwargs):
        data = {
            'id': container_id
        }
        data.update(kwargs)
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
        log_stream = self.docker._multiplexed_result(response)
        if follow:
            return log_stream
        log_lines = []

        #TODO 3.5 cleans up this syntax
        i = yield from log_stream.__aiter__()
        while True:
            try:
                line = yield from i.__anext__()
            except StopAsyncIteration:
                break
            else:
                log_lines.append(line.decode('utf-8'))

        return ''.join(log_lines)

    @asyncio.coroutine
    def copy(self, resource, **kwargs):
        #TODO this is deprecated, use get_archive instead
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
    def put_archive(self, path, data):
        response = yield from self.docker._query(
            "containers/{}/archive".format(self._id),
            method='PUT',
            data=data,
            headers={"content-type": "application/json",},
            params={'path': path}
        )
        data = yield from self.docker._result(response)
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
    def start(self, _config=None, **config):
        config = _config or config
        config = json.dumps(config, sort_keys=True, indent=4).encode('utf-8')
        response = yield from self.docker._query(
            "containers/{}/start".format(self._id),
            method='POST',
            headers={"content-type": "application/json",},
            data=config
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

    @asyncio.coroutine
    def port(self, private_port):
        if 'NetworkSettings' not in self._container:
            yield from self.show()

        private_port = str(private_port)
        h_ports = None

        # Port settings is None when the container is running with
        # network_mode=host.
        port_settings = self._container.get('NetworkSettings', {}).get('Ports')
        if port_settings is None:
            return None

        if '/' in private_port:
            return port_settings.get(private_port)

        h_ports = port_settings.get(private_port + '/tcp')
        if h_ports is None:
            h_ports = port_settings.get(private_port + '/udp')

        return h_ports

    def __getitem__(self, key):
        return self._container[key]

    def __hasitem__(self, key):
        return key in self._container


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
    def query(self, **params):
        response = yield from self.docker._query(
            "events",
            method="GET",
            params=params,
        )
        json_stream = yield from self.docker._json_stream_result(response, self._transform_event)
        return json_stream

    def _transform_event(self, data):
        if 'time' in data:
            data['time'] = dt.datetime.fromtimestamp(data['time'])
        return data

    @asyncio.coroutine
    def run(self):
        self.running = True
        containers = self.docker.containers
        json_stream = yield from self.query()


        i = yield from json_stream.__aiter__()
        while True:
            try:
                data = yield from i.__anext__()
            except StopAsyncIteration:
                break
            else:
                if 'id' in data and data['status'] in [
                    "start", "create",
                ]:
                    data['container'] = yield from containers.get(data['id'])

                asyncio.async(self.channel.put(data))
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

        yield from response.release()

        self.running = False
