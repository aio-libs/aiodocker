import asyncio
import base64
from collections import ChainMap
import datetime as dt
import io
import json
import logging
import os
from pathlib import Path
import re
import ssl
import tarfile
import warnings

import aiohttp
from yarl import URL

from .channel import Channel
from .exceptions import DockerError
from .utils import identical, human_bool, httpize
from .multiplexed import multiplexed_result
from .jsonstream import json_stream_result

log = logging.getLogger(__name__)

_sock_search_paths = [
    Path('/run/docker.sock'),
    Path('/var/run/docker.sock'),
]

_rx_version = re.compile(r'^v\d+\.\d+$')
_rx_tcp_schemes = re.compile(r'^(tcp|http)://')


class Docker:
    def __init__(self,
                 url=None,
                 connector=None,
                 session=None,
                 ssl_context=None,
                 api_version='v1.26'):

        docker_host = url  # rename
        if docker_host is None:
            docker_host = os.environ.get('DOCKER_HOST', None)
        if docker_host is None:
            for sockpath in _sock_search_paths:
                if sockpath.is_socket():
                    docker_host = 'unix://' + str(sockpath)
                    break
        self.docker_host = docker_host

        assert _rx_version.search(api_version) is not None, 'Invalid API version format'
        self.api_version = api_version

        if connector is None:
            if _rx_tcp_schemes.search(docker_host):
                if os.environ.get('DOCKER_TLS_VERIFY', '0') == '1':
                    ssl_context = self._docker_machine_ssl_context()
                    docker_host = _rx_tcp_schemes.sub('https://', docker_host)
                else:
                    ssl_context = None
                connector = aiohttp.TCPConnector(ssl_context=ssl_context)
                self.docker_host = docker_host
            elif docker_host.startswith('unix://'):
                connector = aiohttp.UnixConnector(docker_host[7:])
                self.docker_host = "unix://localhost"  # dummy hostname for URL composition
            else:
                raise ValueError('Missing protocol scheme in docker_host.')
        self.connector = connector
        if session is None:
            session = aiohttp.ClientSession(connector=self.connector)
        self.session = session

        self.events = DockerEvents(self)
        self.containers = DockerContainers(self)
        self.images = DockerImages(self)
        self.volumes = DockerVolumes(self)

    async def close(self):
        self.session.close()  # no longer coroutine since aiohttp 2.x

    async def auth(self, **credentials):
        response = await self._query_json(
            "auth", "POST",
            data=credentials,
            headers={"content-type": "application/json",},
        )
        return response

    async def version(self):
        data = await self._query_json("version")
        return data

    async def pull(self, image, stream=False):
        response = await self._query(
            "images/create", "POST",
            params={"fromImage": image},
            headers={"content-type": "application/json",},
        )
        return (await json_stream_result(response, stream=stream))

    def canonicalize_url(self, path, query=None):
        url = URL(f"{self.docker_host}/{self.api_version}/{path}")
        url = url.with_query(httpize(query))
        return url

    async def _query(self, path, method='GET', params=None, timeout=None,
                     data=None, headers=None, **kwargs):
        '''
        Get the response object by performing the HTTP request.
        The caller is responsible to finalize the response object.
        '''
        url = self.canonicalize_url(path)
        try:
            with aiohttp.Timeout(timeout):
                response = await self.session.request(
                    method, url,
                    params=httpize(params), headers=headers,
                    data=data, **kwargs)
        except asyncio.TimeoutError:
            raise

        if (response.status // 100) in [4, 5]:
            what = await response.read()
            content_type = response.headers.get('content-type','')
            response.close()
            if content_type == 'application/json':
                raise DockerError(response.status, json.loads(what.decode('utf8')))
            else:
                raise DockerError(response.status, {"message": what.decode('utf8')})

        return response

    @staticmethod
    async def _result(response, response_type=None):
        '''
        Convert the response to native objects by the given response type
        or the auto-detected HTTP content-type.
        It also ensures release of the response object.
        '''
        try:
            if not response_type:
                ct = response.headers.get("Content-Type", "")
                if 'json' in ct:
                    response_type = 'json'
                elif 'x-tar' in ct:
                    response_type = 'tar'
                elif 'text/plain' in ct:
                    response_type = 'text'
                else:
                    raise TypeError(f"Unrecognized response type: {ct}")
            if 'tar' == response_type:
                what = await response.read()
                return tarfile.open(mode='r', fileobj=io.BytesIO(what))
            if 'json' == response_type:
                data = await response.json(encoding='utf-8')
            elif 'text' ==  response_type:
                data = await response.text(encoding='utf-8')
            else:
                data = await response.read()
            return data
        finally:
            await response.release()

    async def _websocket(self, path, **params):
        if not params:
            params = {
                'stdin': True,
                'stdout': True,
                'stderr': True,
                'stream': True
            }
        url = self.canonicalize_url(path, query=params)
        ws = await self.session.ws_connect(url,
            protocols=['chat'], origin='http://localhost',
            autoping=True, autoclose=True)
        return ws

    async def _query_json(self, *args, **kwargs):
        '''
        A shorthand of _query() followed by _result() with JSON response type.
        '''
        response = await self._query(*args, **kwargs)
        data = await Docker._result(response, 'json')
        return data

    @staticmethod
    def _docker_machine_ssl_context():
        '''
        Create a SSLContext object using DOCKER_* env vars.
        '''
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.set_ciphers(ssl._RESTRICTED_SERVER_CIPHERS)
        certs_path = os.environ.get('DOCKER_CERT_PATH', None)
        if certs_path is None:
            raise ValueError('Cannot create ssl context, DOCKER_CERT_PATH is not set!')
        certs_path = Path(certs_path)
        context.load_verify_locations(cafile=certs_path / 'ca.pem')
        context.load_cert_chain(certfile=certs_path / 'cert.pem', keyfile=certs_path / 'key.pem')
        return context


class DockerImages(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self, **params):
        response = await self.docker._query_json(
            "images/json", "GET",
            params=params,
            headers={"content-type": "application/json",},
        )
        return response

    async def get(self, name):
        response = await self.docker._query_json(
            f"images/{name}/json",
            headers={"content-type": "application/json",},
        )
        return response

    async def history(self, name):
        response = await self.docker._query_json(
            f"images/{name}/history",
            headers={"content-type": "application/json",},
        )
        return response

    async def push(self, name, tag=None, auth=None, stream=False):
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
        response = await self.docker._query(
            f"images/{name}/push",
            "POST",
            params=params,
            headers=headers,
        )
        return (await json_stream_result(response, stream=stream))

    async def tag(self, name, tag=None, repo=None):
        params = {}
        if tag:
            params['tag'] = tag
        if repo:
            params['repo'] = repo
        response = await self.docker._query_json(
            f"images/{name}/tag",
            "POST",
            params=params,
            headers={"content-type": "application/json"},
        )
        return response

    async def delete(self, name, **params):
        response = await self.docker._query_json(
            f"images/{name}/tag",
            "DELETE",
            params=params,
            headers={"content-type": "application/json",},
        )
        return response


class DockerContainers(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self, **kwargs):
        data = await self.docker._query_json(
            "containers/json",
            method='GET',
            params=kwargs
        )
        return [DockerContainer(self.docker, **x) for x in data]

    async def create_or_replace(self, name, config):
        container = None

        try:
            container = await self.get(name)
            if not identical(config, container._container):
                running = container._container.get(
                    "State", {}).get("Running", False)
                if running:
                    await container.stop()
                await container.delete()
                container = None
        except DockerError:
            pass

        if container is None:
            container = await self.create(config, name=name)

        return container

    async def create(self, config, name=None):
        url = "containers/create"

        config = json.dumps(config, sort_keys=True).encode('utf-8')
        kwargs = {}
        if name:
            kwargs['name'] = name
        data = await self.docker._query_json(
            url,
            method='POST',
            headers={"content-type": "application/json",},
            data=config,
            params=kwargs
        )
        return DockerContainer(self.docker, id=data['Id'])

    async def run(self, config, name=None):

        try:
            container = await self.create(config, name)
        except DockerError as e:

            # image not find, try pull it

            if e.status == 404:

                if 'Image' in config:
                    try:
                        await self.docker.pull(config['Image'])
                    except DockerError as e:
                        raise e

                    container = await self.create(config, name)
            else:
                raise e
        await container.start()
        return container

    async def get(self, container, **kwargs):
        data = await self.docker._query_json(
            f"containers/{container}/json",
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

    async def log(self, stdout=False, stderr=False, follow=False, **kwargs):
        if stdout is False and stderr is False:
            raise TypeError("Need one of stdout or stderr")

        params = {
            "stdout": stdout,
            "stderr": stderr,
            "follow": follow,
        }
        params.update(kwargs)

        inspect_info = await self.show()
        is_tty = inspect_info['Config']['Tty']

        response = await self.docker._query(
            f"containers/{self._id}/logs",
            method='GET',
            params=params,
        )
        return (await multiplexed_result(response, follow, is_tty=is_tty))

    async def copy(self, resource, **kwargs):
        #TODO this is deprecated, use get_archive instead
        request = json.dumps({
            "Resource": resource,
        }, sort_keys=True).encode('utf-8')
        data = await self.docker._query(
            f"containers/{self._id}/copy",
            method='POST',
            data=request,
            headers={"content-type": "application/json",},
            params=kwargs
        )
        return data

    async def put_archive(self, path, data):
        response = await self.docker._query(
            f"containers/{self._id}/archive",
            method='PUT',
            data=data,
            headers={"content-type": "application/json",},
            params={'path': path}
        )
        data = await Docker._result(response)
        return data

    async def show(self, **kwargs):
        data = await self.docker._query_json(
            f"containers/{self._id}/json",
            method='GET',
            params=kwargs
        )
        self._container = data
        return data

    async def stop(self, **kwargs):
        response = await self.docker._query(
            f"containers/{self._id}/stop",
            method='POST',
            params=kwargs
        )
        await response.release()
        return

    async def start(self, **kwargs):
        response = await self.docker._query(
            f"containers/{self._id}/start",
            method='POST',
            headers={"content-type": "application/json",},
            data=kwargs
        )
        await response.release()
        return

    async def kill(self, **kwargs):
        response = await self.docker._query(
            f"containers/{self._id}/kill",
            method='POST',
            params=kwargs
        )
        await response.release()
        return

    async def wait(self, timeout=None, **kwargs):
        data = await self.docker._query_json(
            f"containers/{self._id}/wait",
            method='POST',
            params=kwargs,
            timeout=timeout,
        )
        return data

    async def delete(self, **kwargs):
        response = await self.docker._query(
            f"containers/{self._id}",
            method='DELETE',
            params=kwargs
        )
        await response.release()
        return

    async def websocket(self, **params):
        path = f"containers/{self._id}/attach/ws"
        ws = await self.docker._websocket(path, **params)
        return ws

    async def port(self, private_port):
        if 'NetworkSettings' not in self._container:
            await self.show()

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

    async def stats(self, stream=True):
        if stream:
            response = await self.docker._query(
                f"containers/{self._id}/stats",
                params={'stream': '1'},
            )
            return (await json_stream_result(response))
        else:
            data = await self.docker._query_json(
                f"containers/{self._id}/stats",
                params={'stream': '0'},
            )
            return data

    def __getitem__(self, key):
        return self._container[key]

    def __hasitem__(self, key):
        return key in self._container


class DockerEvents:
    def __init__(self, docker):
        self.docker = docker
        self.channel = Channel()
        self.json_stream = None

    def listen(self):
        warnings.warn("use subscribe() method instead",
                      DeprecationWarning, stacklevel=2)
        return self.channel.subscribe()

    def subscribe(self):
        return self.channel.subscribe()

    def _transform_event(self, data):
        if 'time' in data:
            data['time'] = dt.datetime.fromtimestamp(data['time'])
        return data

    async def run(self, **params):
        if self.json_stream:
            warnings.warn("already running",
                          RuntimeWarning, stackelevel=2)
            return
        forced_params = {
            'stream': True,
        }
        params = ChainMap(forced_params, params)
        try:
            response = await self.docker._query(
                "events",
                method="GET",
                params=params,
            )
            self.json_stream = await json_stream_result(response,
                self._transform_event,
                human_bool(params['stream']),
            )
            async for data in self.json_stream.fetch():
                await self.channel.publish(data)
        finally:
            # signal termination to subscribers
            await self.channel.publish(None)
            try:
                await self.json_stream.close()
            except:
                pass
            self.json_stream = None

    async def stop(self):
        if self.json_stream:
            await self.json_stream.close()


class DockerLog:
    def __init__(self, docker, container):
        self.docker = docker
        self.channel = Channel()
        self.container = container
        self.response = None

    def listen(self):
        warnings.warn("use subscribe() method instead",
                      DeprecationWarning, stacklevel=2)
        return self.channel.subscribe()

    def subscribe(self):
        return self.channel.subscribe()

    async def run(self, **params):
        if self.response:
            warnings.warn("already running",
                          RuntimeWarning, stackelevel=2)
            return
        forced_params = {
            'follow': True,
        }
        default_params = {
            'stdout': True,
            'stderr': True,
        }
        params = ChainMap(forced_params, params, default_params)
        try:
            self.response = await self.docker._query(
                f'containers/{self.container._id}/logs',
                params=params,
            )
            while True:
                msg = await self.response.content.readline()
                if not msg:
                    break
                await self.channel.publish(msg)
        except (aiohttp.ClientConnectionError,
                aiohttp.ServerDisconnectedError):
            pass
        finally:
            # signal termination to subscribers
            await self.channel.publish(None)
            try:
                await self.response.release()
            except:
                pass
            self.response = None

    async def stop(self):
        if self.response:
            await self.response.release()


class DockerVolumes:
    def __init__(self, docker):
        self.docker = docker

    async def list(self):
        data = await self.docker._query_json("volumes")
        return data

    async def create(self, config):
        config = json.dumps(config, sort_keys=True).encode('utf-8')
        data = await self.docker._query_json(
            "volumes/create",
            method="POST",
            headers={"content-type": "application/json",},
            data=config,
        )
        return DockerVolume(self.docker, data['Name'])


class DockerVolume:
    def __init__(self, docker, name):
        self.docker = docker
        self.name = name

    async def show(self):
        data = await self.docker._query_json(
            f"volumes/{self.name}"
        )
        return data

    async def delete(self):
        response = await self.docker._query(
            f"volumes/{self.name}",
            method="DELETE",
        )
        await response.release()
        return
