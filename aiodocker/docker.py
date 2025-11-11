from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import ssl
import sys
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Optional,
    Type,
    Union,
)

import aiohttp
from multidict import CIMultiDict
from yarl import URL

# Sub-API classes
from .configs import DockerConfigs
from .containers import DockerContainer, DockerContainers
from .events import DockerEvents
from .exceptions import DockerError
from .images import DockerImages
from .logs import DockerLog
from .networks import DockerNetwork, DockerNetworks
from .nodes import DockerSwarmNodes
from .secrets import DockerSecrets
from .services import DockerServices
from .swarm import DockerSwarm
from .system import DockerSystem
from .tasks import DockerTasks
from .types import SENTINEL, JSONObject, Sentinel, Timeout
from .utils import httpize, parse_result
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
    "DockerConfigs",
    "DockerSecrets",
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

_sock_search_paths = [
    Path("/run/docker.sock"),
    Path("/var/run/docker.sock"),
    Path.home() / ".docker/run/docker.sock",
]

_rx_version = re.compile(r"^v\d+\.\d+$")
_rx_tcp_schemes = re.compile(r"^(tcp|http|https)://")


class Docker:
    """
    The Docker client as the main entrypoint to the sub-APIs such as
    container, images, networks, swarm and services, etc.
    You may access such sub-API collections via the attributes of the client instance,
    like:

    .. code-block:: python

        docker = aiodocker.Docker()
        await docker.containers.list()
        await docker.images.pull(...)

    The client will auto-detect the Docker host from the ``DOCKER_HOST`` environment
    variable or search for local socket files if not specified.

    Args:
        url: The Docker daemon address as the full URL string (e.g.,
            ``"unix:///var/run/docker.sock"``, ``"tcp://127.0.0.1:2375"``,
            ``"npipe:////./pipe/docker_engine"``).
            If not specified, it will use ``DOCKER_HOST`` environment variable or auto-detect
            from common socket paths.
        connector: Custom aiohttp connector for the HTTP session. If provided,
            it will be used instead of creating a connector based on the url.
        session: Custom aiohttp ClientSession. If None, a new session will be
            created with the connector and timeout settings.
        timeout: :class:`~aiodocker.types.Timeout` configuration for API requests.
            If None, there is no timeout at all.
        ssl_context: SSL context for HTTPS connections. If None and ``DOCKER_TLS_VERIFY``
            is set, will create a context using ``DOCKER_CERT_PATH`` certificates.
        api_version: Pin the Docker API version (e.g., "v1.43"). Use "auto" to
            automatically detect the API version from the daemon.

    Raises:
        ValueError: Raised if the docker host cannot be determined,
            if both url and connector are incompatible,
            or if api_version format is invalid.
        OSError: On Windows, if named pipe access fails unexpectedly.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        connector: Optional[aiohttp.BaseConnector] = None,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: Optional[Timeout] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
        api_version: str = "auto",
    ) -> None:
        docker_host = url  # rename
        if docker_host is None:
            docker_host = os.environ.get("DOCKER_HOST", None)
        if docker_host is None:
            if sys.platform == "win32":
                try:
                    if Path(r"\\.\pipe\docker_engine").exists():
                        docker_host = "npipe:////./pipe/docker_engine"
                    else:
                        # The default address used by Docker Client on Windows
                        docker_host = "https://127.0.0.1:2376"
                except OSError as ex:
                    if ex.winerror == 231:  # type: ignore
                        # All pipe instances are busy
                        # but the pipe definitely exists
                        docker_host = "npipe:////./pipe/docker_engine"
                    else:
                        raise
            else:
                for sockpath in _sock_search_paths:
                    if sockpath.is_socket():
                        docker_host = "unix://" + str(sockpath)
                        break

        assert docker_host is not None
        self.docker_host = docker_host

        if api_version != "auto" and _rx_version.search(api_version) is None:
            raise ValueError("Invalid API version format")
        self.api_version = api_version

        self._timeout = timeout or Timeout()

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
                if (
                    os.environ.get("DOCKER_TLS_VERIFY", "0") == "1"
                    and ssl_context is None
                ):
                    ssl_context = self._docker_machine_ssl_context()
                    docker_host = _rx_tcp_schemes.sub("https://", docker_host)
                connector = aiohttp.TCPConnector(ssl=ssl_context)  # type: ignore[arg-type]
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
            session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self._timeout.to_aiohttp_client_timeout(),
            )
        self.session = session

        self.events = DockerEvents(self)
        self.containers = DockerContainers(self)
        self.swarm = DockerSwarm(self)
        self.services = DockerServices(self)
        self.configs = DockerConfigs(self)
        self.secrets = DockerSecrets(self)
        self.tasks = DockerTasks(self)
        self.images = DockerImages(self)
        self.volumes = DockerVolumes(self)
        self.networks = DockerNetworks(self)
        self.nodes = DockerSwarmNodes(self)
        self.system = DockerSystem(self)

        # legacy aliases
        self.pull = self.images.pull
        self.push = self.images.push

    async def __aenter__(self) -> Docker:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the Docker client and release resources.

        Stops the event monitoring and closes the underlying aiohttp session,
        releasing all associated resources including connections.
        """
        await self.events.stop()
        await self.session.close()

    async def auth(self, **credentials: Any) -> dict[str, Any]:
        """Authenticate with Docker registry.

        Validates registry credentials and returns authentication information.

        Args:
            credentials: Registry authentication credentials. Typically includes:

                - ``username`` (str): Registry username
                - ``password`` (str): Registry password
                - ``email`` (str, optional): User email
                - ``serveraddress`` (str, optional): Registry server address

        Returns:
            Authentication response from the Docker daemon, typically
            containing status and identity token information.

        Raises:
            DockerError: If authentication fails or credentials are invalid.
        """
        response = await self._query_json("auth", "POST", data=credentials)
        return response

    async def version(self) -> dict[str, Any]:
        """Get Docker daemon version information.

        Retrieves version details about the Docker daemon including API version,
        OS, architecture, and component versions.

        Returns:
            A dict containing version information with keys like:

            - ``Version`` (str): Docker version
            - ``ApiVersion`` (str): API version
            - ``Os`` (str): Operating system
            - ``Arch`` (str): Architecture
            - ``KernelVersion`` (str): Kernel version
            - ``GitCommit`` (str): Git commit hash

            and additional component-specific information.

        Raises:
            DockerError: If the request fails or daemon is unreachable.
        """
        data = await self._query_json("version")
        return data

    def _canonicalize_url(
        self, path: Union[str, URL], *, versioned_api: bool = True
    ) -> URL:
        if isinstance(path, URL):
            assert not path.is_absolute()
        if versioned_api:
            return URL(
                "{self.docker_host}/{self.api_version}/{path}".format(
                    self=self, path=path
                )
            )
        else:
            return URL(f"{self.docker_host}/{path}")

    async def _check_version(self) -> None:
        if self.api_version == "auto":
            ver = await self._query_json("version", versioned_api=False)
            self.api_version = "v" + str(ver["ApiVersion"])

    @asynccontextmanager
    async def _query(
        self,
        path: str | URL,
        method: str = "GET",
        *,
        params: Optional[JSONObject] = None,
        data: Optional[Any] = None,
        headers: Optional[Mapping[str, str | int | bool]] = None,
        timeout: float | aiohttp.ClientTimeout | None | Sentinel = SENTINEL,
        chunked: Optional[bool] = None,
        read_until_eof: bool = True,
        versioned_api: bool = True,
    ) -> AsyncIterator[aiohttp.ClientResponse]:
        """
        Get the response object by performing the HTTP request.
        The caller is responsible to finalize the response object
        via the async context manager protocol.
        """
        yield await self._do_query(
            path=path,
            method=method,
            params=params,
            data=data,
            headers=headers,
            timeout=timeout,
            chunked=chunked,
            read_until_eof=read_until_eof,
            versioned_api=versioned_api,
        )

    async def _do_query(
        self,
        path: str | URL,
        method: str,
        *,
        params: Optional[JSONObject] = None,
        data: Any = None,
        headers: Optional[Mapping[str, str | int | bool]] = None,
        timeout: float | aiohttp.ClientTimeout | None | Sentinel = SENTINEL,
        chunked: Optional[bool] = None,
        read_until_eof: bool = True,
        versioned_api: bool = True,
    ) -> aiohttp.ClientResponse:
        if versioned_api:
            await self._check_version()
        url = self._canonicalize_url(path, versioned_api=versioned_api)
        _headers: CIMultiDict[str | int | bool] = CIMultiDict()
        if headers:
            _headers.update(headers)
        if "Content-Type" not in _headers:
            _headers["Content-Type"] = "application/json"
        if timeout is SENTINEL:
            # Use the timeout configured upon the Docker instance creation
            # or the timeout already configured in the passed aiohttp.ClientSession instance.
            timeout = self.session.timeout
        assert not isinstance(timeout, Sentinel)
        # Set the timeout manually according to the individual timeout argument.
        # NOTE: This is no longer recommended.
        #       Use `asyncio.timeout()` async context manager block to enforce
        #       the total request-response processing timeout.
        if not isinstance(timeout, aiohttp.ClientTimeout):
            timeout = aiohttp.ClientTimeout(timeout)
        try:
            real_params = httpize(params)
            real_headers = httpize(_headers)
            response = await self.session.request(
                method,
                url,
                params=real_params,
                headers=real_headers,
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
                        f"[{exc}]"
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
        path: str | URL,
        method: str = "GET",
        *,
        params: Optional[JSONObject] = None,
        data: Optional[Any] = None,
        headers: Optional[Mapping[str, str | int | bool]] = None,
        timeout: float | aiohttp.ClientTimeout | None | Sentinel = SENTINEL,
        read_until_eof: bool = True,
        versioned_api: bool = True,
    ) -> Any:
        """
        A shorthand of _query() that treats the input as JSON.
        """
        _headers: CIMultiDict[str | int | bool] = CIMultiDict()
        if headers:
            _headers.update(headers)
        if "Content-Type" not in _headers:
            _headers["Content-Type"] = "application/json"
        if data is not None and not isinstance(data, (str, bytes)):
            data = json.dumps(data)
        async with self._query(
            path,
            method,
            params=params,
            data=data,
            headers=_headers,
            timeout=timeout,
            read_until_eof=read_until_eof,
            versioned_api=versioned_api,
        ) as response:
            data = await parse_result(response)
            return data

    def _query_chunked_post(
        self,
        path: str | URL,
        method: str = "POST",
        *,
        params: Optional[JSONObject] = None,
        data: Optional[Any] = None,
        headers: Optional[Mapping[str, str | int | bool]] = None,
        timeout: Union[float, aiohttp.ClientTimeout, Sentinel, None] = SENTINEL,
        read_until_eof: bool = True,
        versioned_api: bool = True,
    ) -> AbstractAsyncContextManager[aiohttp.ClientResponse]:
        """
        A shorthand for uploading data by chunks
        """
        _headers: CIMultiDict[str | int | bool] = CIMultiDict()
        if headers:
            _headers.update(headers)
        if "Content-Type" not in _headers:
            _headers["Content-Type"] = "application/octet-stream"
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

    async def _websocket(
        self, path: Union[str, URL], **params: Any
    ) -> aiohttp.ClientWebSocketResponse:
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
    def _docker_machine_ssl_context() -> ssl.SSLContext:
        """
        Create a SSLContext object using DOCKER_* env vars.
        """
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        context.set_ciphers(ssl._RESTRICTED_SERVER_CIPHERS)  # type: ignore
        certs_path = os.environ.get("DOCKER_CERT_PATH", None)
        if certs_path is None:
            raise ValueError("Cannot create ssl context, DOCKER_CERT_PATH is not set!")
        certs_path2 = Path(certs_path)
        context.load_verify_locations(cafile=str(certs_path2 / "ca.pem"))
        context.load_cert_chain(
            certfile=str(certs_path2 / "cert.pem"), keyfile=str(certs_path2 / "key.pem")
        )
        return context
