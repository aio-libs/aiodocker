import asyncio
import json
import logging
import os
from pathlib import Path
import re
import ssl

import aiohttp
from yarl import URL

from .utils import httpize, parse_result

# Sub-API classes
from .containers import DockerContainers, DockerContainer
from .events import DockerEvents
from .exceptions import DockerError
from .images import DockerImages
from .logs import DockerLog
from .swarm import DockerSwarm
from .services import DockerServices
from .tasks import DockerTasks
from .volumes import DockerVolumes, DockerVolume

__all__ = (
    'Docker',
    'DockerContainers', 'DockerContainer',
    'DockerEvents',
    'DockerError',
    'DockerImages',
    'DockerLog',
    'DockerSwarm',
    'DockerServices',
    'DockerTasks',
    'DockerVolumes', 'DockerVolume',
)

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

        assert _rx_version.search(api_version) is not None, \
            'Invalid API version format'
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
                # dummy hostname for URL composition
                self.docker_host = "unix://localhost"
            else:
                raise ValueError('Missing protocol scheme in docker_host.')
        self.connector = connector
        if session is None:
            session = aiohttp.ClientSession(connector=self.connector)
        self.session = session

        self.events = DockerEvents(self)
        self.containers = DockerContainers(self)
        self.swarm = DockerSwarm(self)
        self.services = DockerServices(self)
        self.tasks = DockerTasks(self)
        self.images = DockerImages(self)
        self.volumes = DockerVolumes(self)

        # legacy aliases
        self.pull = self.images.pull
        self.push = self.images.push

    async def close(self):
        await self.events.stop()
        await self.session.close()

    async def auth(self, **credentials):
        response = await self._query_json(
            "auth", "POST",
            data=credentials,
        )
        return response

    async def version(self):
        data = await self._query_json("version")
        return data

    def _canonicalize_url(self, path):
        return URL("{self.docker_host}/{self.api_version}/{path}"
                   .format(self=self, path=path))

    async def _query(self, path, method='GET', *,
                     params=None, data=None, headers=None,
                     timeout=None):
        '''
        Get the response object by performing the HTTP request.
        The caller is responsible to finalize the response object.
        '''
        url = self._canonicalize_url(path)
        if headers and 'content-type' not in headers:
            headers['content-type'] = 'application/json'
        try:
            response = await self.session.request(
                method, url,
                params=httpize(params),
                headers=headers,
                data=data,
                timeout=timeout)
        except asyncio.TimeoutError:
            raise
        if (response.status // 100) in [4, 5]:
            what = await response.read()
            content_type = response.headers.get('content-type', '')
            response.close()
            if content_type == 'application/json':
                raise DockerError(response.status,
                                  json.loads(what.decode('utf8')))
            else:
                raise DockerError(response.status,
                                  {"message": what.decode('utf8')})
        return response

    async def _query_json(self, path, method='GET', *,
                          params=None, data=None, headers=None,
                          timeout=None):
        '''
        A shorthand of _query() that treats the input as JSON.
        '''
        if headers is None:
            headers = {}
        headers['content-type'] = 'application/json'
        if not isinstance(data, (str, bytes)):
            data = json.dumps(data)
        response = await self._query(
            path, method,
            params=params, data=data, headers=headers,
            timeout=timeout)
        data = await parse_result(response, 'json')
        return data

    async def _websocket(self, path, **params):
        if not params:
            params = {
                'stdin': True,
                'stdout': True,
                'stderr': True,
                'stream': True
            }
        url = self._canonicalize_url(path)
        # ws_connect() does not have params arg.
        url = url.with_query(httpize(params))
        ws = await self.session.ws_connect(
            url,
            protocols=['chat'],
            origin='http://localhost',
            autoping=True,
            autoclose=True)
        return ws

    @staticmethod
    def _docker_machine_ssl_context():
        '''
        Create a SSLContext object using DOCKER_* env vars.
        '''
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.set_ciphers(ssl._RESTRICTED_SERVER_CIPHERS)
        certs_path = os.environ.get('DOCKER_CERT_PATH', None)
        if certs_path is None:
            raise ValueError("Cannot create ssl context, "
                             "DOCKER_CERT_PATH is not set!")
        certs_path = Path(certs_path)
        context.load_verify_locations(cafile=certs_path / 'ca.pem')
        context.load_cert_chain(certfile=certs_path / 'cert.pem',
                                keyfile=certs_path / 'key.pem')
        return context
