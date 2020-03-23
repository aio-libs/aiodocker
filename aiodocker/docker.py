import asyncio
import json
import logging
import os
import re
import ssl
import sys
from pathlib import Path

import aiohttp
from multidict import CIMultiDict
from yarl import URL

# Sub-API classes
from .containers import DockerContainer, DockerContainers
from .events import DockerEvents
from .exceptions import DockerError
from .images import DockerImages
from .logs import DockerLog
from .networks import DockerNetwork, DockerNetworks
from .nodes import DockerSwarmNodes
from .services import DockerServices
from .swarm import DockerSwarm
from .system import DockerSystem
from .tasks import DockerTasks
from .utils import _AsyncCM, httpize, parse_result
from .volumes import DockerVolume, DockerVolumes


__all__ = (
    "Docker",
    "DockerContainers",
    "DockerContainer",
    "DockerEvents",
    "DockerError",
    "DockerImages",
    "DockerLog",
    "DockerSwarm",
    "DockerServices",
    "DockerTasks",
    "DockerVolumes",
    "DockerVolume",
    "DockerNetworks",
    "DockerNetwork",
    "DockerSwarmNodes",
    "DockerSystem",
)

log = logging.getLogger(__name__)

_sock_search_paths = [Path("/run/docker.sock"), Path("/var/run/docker.sock")]

_rx_version = re.compile(r"^v\d+\.\d+$")
_rx_tcp_schemes = re.compile(r"^(tcp|http)://")


class Docker:
    def __init__(
        self,
        url=None,
        connector=None,
        session=None,
        ssl_context=None,
        api_version="v1.35",
    ):

        docker_host = url  # rename
        if docker_host is None:
            docker_host = os.environ.get("DOCKER_HOST", None)
        if docker_host is None:
            for sockpath in _sock_search_paths:
                if sockpath.is_socket():
                    docker_host = "unix://" + str(sockpath)
                    break
        if docker_host is None and sys.platform == "win32":
            try:
                if Path("\\\\.\\pipe\\docker_engine").exists():
                    docker_host = "npipe:////./pipe/docker_engine"
            except OSError as ex:
                if ex.winerror == 231:
                    # All pipe instances are busy
                    # but the pipe definitely exists
                    docker_host = "npipe:////./pipe/docker_engine"
                else:
                    raise
        self.docker_host = docker_host

        assert _rx_version.search(api_version) is not None, "Invalid API version format"
        self.api_version = api_version

        if docker_host is None:
            raise ValueError(
                "Missing valid docker_host."
                "Either DOCKER_HOST or local sockets are not available."
            )

        self._connection_info = docker_host
        if connector is None:
            UNIX_PRE = "unix://"
            UNIX_PRE_LEN = len(UNIX_PRE)
            WIN_PRE = "npipe://"
            WIN_PRE_LEN = len(WIN_PRE)
            if _rx_tcp_schemes.search(docker_host):
                if os.environ.get("DOCKER_TLS_VERIFY", "0") == "1":
                    ssl_context = self._docker_machine_ssl_context()
                    docker_host = _rx_tcp_schemes.sub("https://", docker_host)
                else:
                    ssl_context = None
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                self.docker_host = docker_host
            elif docker_host.startswith(UNIX_PRE):
                connector = aiohttp.UnixConnector(docker_host[UNIX_PRE_LEN:])
                # dummy hostname for URL composition
                self.docker_host = UNIX_PRE + "localhost"
            elif docker_host.startswith(WIN_PRE):
                connector = aiohttp.NamedPipeConnector(
                    docker_host[WIN_PRE_LEN:].replace("/", "\\")
                )
                # dummy hostname for URL composition
                self.docker_host = WIN_PRE + "localhost"
            else:
                raise ValueError("Missing protocol scheme in docker_host.")
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
        self.networks = DockerNetworks(self)
        self.nodes = DockerSwarmNodes(self)
        self.system = DockerSystem(self)

        # legacy aliases
        self.pull = self.images.pull
        self.push = self.images.push

    async def close(self):
        await self.events.stop()
        await self.session.close()

    async def auth(self, **credentials):
        response = await self._query_json("auth", "POST", data=credentials)
        return response

    async def version(self):
        data = await self._query_json("version")
        return data

    def _canonicalize_url(self, path):
        return URL(
            "{self.docker_host}/{self.api_version}/{path}".format(self=self, path=path)
        )

    def _query(
        self,
        path,
        method="GET",
        *,
        params=None,
        data=None,
        headers=None,
        timeout=None,
        chunked=None,
        read_until_eof=True,
    ):
        """
        Get the response object by performing the HTTP request.
        The caller is responsible to finalize the response object.
        """
        return _AsyncCM(
            self._do_query(
                path=path,
                method=method,
                params=params,
                data=data,
                headers=headers,
                timeout=timeout,
                chunked=chunked,
                read_until_eof=read_until_eof,
            )
        )

    async def _do_query(
        self, path, method, *, params, data, headers, timeout, chunked, read_until_eof
    ):
        url = self._canonicalize_url(path)
        if headers:
            headers = CIMultiDict(headers)
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
        try:
            real_params = httpize(params)
            response = await self.session.request(
                method,
                url,
                params=real_params,
                headers=headers,
                data=data,
                timeout=timeout,
                chunked=chunked,
                read_until_eof=read_until_eof,
            )
        except asyncio.TimeoutError:
            raise
        except aiohttp.ClientConnectionError as exc:
            raise DockerError(
                900,
                {
                    "message": (
                        f"Cannot connect to Docker Engine via {self._connection_info} "
                        f"[{exc.os_error.strerror}]"
                    )
                },
            )
        if (response.status // 100) in [4, 5]:
            what = await response.read()
            content_type = response.headers.get("content-type", "")
            response.close()
            if content_type == "application/json":
                raise DockerError(response.status, json.loads(what.decode("utf8")))
            else:
                raise DockerError(response.status, {"message": what.decode("utf8")})
        return response

    async def _query_json(
        self,
        path,
        method="GET",
        *,
        params=None,
        data=None,
        headers=None,
        timeout=None,
        read_until_eof=True,
    ):
        """
        A shorthand of _query() that treats the input as JSON.
        """
        if headers is None:
            headers = {}
        headers["Content-Type"] = "application/json"
        if not isinstance(data, (str, bytes)):
            data = json.dumps(data)
        async with self._query(
            path,
            method,
            params=params,
            data=data,
            headers=headers,
            timeout=timeout,
            read_until_eof=read_until_eof,
        ) as response:
            data = await parse_result(response)
            return data

    def _query_chunked_post(
        self,
        path,
        method="POST",
        *,
        params=None,
        data=None,
        headers=None,
        timeout=None,
        read_until_eof=True,
    ):
        """
        A shorthand for uploading data by chunks
        """
        if headers is None:
            headers = {}
        if headers and "content-type" not in headers:
            headers["content-type"] = "application/octet-stream"
        return self._query(
            path,
            method,
            params=params,
            data=data,
            headers=headers,
            timeout=timeout,
            chunked=True,
            read_until_eof=read_until_eof,
        )

    async def _websocket(self, path, **params):
        if not params:
            params = {"stdin": True, "stdout": True, "stderr": True, "stream": True}
        url = self._canonicalize_url(path)
        # ws_connect() does not have params arg.
        url = url.with_query(httpize(params))
        ws = await self.session.ws_connect(
            url,
            protocols=["chat"],
            origin="http://localhost",
            autoping=True,
            autoclose=True,
        )
        return ws

    @staticmethod
    def _docker_machine_ssl_context():
        """
        Create a SSLContext object using DOCKER_* env vars.
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.set_ciphers(ssl._RESTRICTED_SERVER_CIPHERS)
        certs_path = os.environ.get("DOCKER_CERT_PATH", None)
        if certs_path is None:
            raise ValueError(
                "Cannot create ssl context, " "DOCKER_CERT_PATH is not set!"
            )
        certs_path = Path(certs_path)
        context.load_verify_locations(cafile=certs_path / "ca.pem")
        context.load_cert_chain(
            certfile=certs_path / "cert.pem", keyfile=certs_path / "key.pem"
        )
        return context
