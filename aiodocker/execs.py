import json
from collections import namedtuple
import struct
import sys
import warnings
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    Optional,
    Type,
    cast,
    overload,
)

import aiohttp
from aiohttp import FlowControlDataQueue
from aiohttp.http_websocket import WebSocketWriter
from typing_extensions import Literal
from yarl import URL


if TYPE_CHECKING:
    from .docker import Docker


if sys.version_info >= (3, 7):
    from contextlib import asynccontextmanager
else:
    from async_generator import asynccontextmanager


# When a Tty is allocated for an "exec" operation, the stdout and stderr are streamed
# straight to the client.
# When a Tty is NOT allocated, then stdout and stderr are multiplexed using the format
# given at
# https://docs.docker.com/engine/api/v1.40/#operation/ContainerAttach under the "Stream
# Format" heading. Note that that documentation is for "docker attach" but the format
# also applies to "docker exec."


class Exec:
    def __init__(self, docker: "Docker", id: str) -> None:
        self.docker = docker
        self._id = id

    @property
    def id(self) -> str:
        return self._id

    async def inspect(self) -> Dict[str, Any]:
        return await self.docker._query_json(f"exec/{self._id}/json")

    async def resize(self, *, h: Optional[int] = None, w: Optional[int] = None) -> None:
        url = URL(f"exec/{self._id}/resize").with_query(h=h, w=w)
        async with self.docker._query(url, method="POST") as resp:
            resp

    @overload
    def start(
        self,
        *,
        timeout: aiohttp.ClientTimeout = None,
        detach: Literal[False],
        tty: bool = False,
    ) -> 'ExecStream':
        pass

    @overload  # noqa
    async def start(
        self,
        *,
        timeout: aiohttp.ClientTimeout = None,
        detach: Literal[True],
        tty: bool = False,
    ) -> bytes:
        pass

    def start(  # noqa
        self, *, timeout=None, detach=False, tty=False,
    ):
        """
        Start this exec instance.
        Args:
            timeout: The timeout in seconds for the request to start the exec instance.
            detach: Indicates whether we should detach from the command (like the `-d`
                option to `docker exec`).
            tty: Indicates whether a TTY should be allocated (like the `-t` option to
                `docker exec`).
        Returns:
            If `detach` is `True`, this method will return the result of the exec
            process as a binary string.
            If `detach` is False, an `aiohttp.ClientWebSocketResponse` will be returned.
            You can use it to send and receive data the same wa as the response of
            "ws_connect" of aiohttp. If `tty` is `False`, then the messages returned
            from `receive*` will have their `extra` attribute set to 1 if the data was
            from stdout or 2 if from stderr.
        """
        if detach:
            return self._start_detached(timeout, tty)
        else:
            return ExecStream(self.docker, self._id, tty, timeout)

    @asynccontextmanager
    async def _start_attached(
        self, timeout: aiohttp.ClientTimeout = None, tty: bool = False,
    ) -> AsyncIterator[aiohttp.ClientWebSocketResponse]:
        body = json.dumps({"Detach": False, "Tty": tty})
        async with self.docker._query(
            f"exec/{self._id}/start",
            method="POST",
            data=body,
            headers={"Connection": "Upgrade", "Upgrade": "tcp"},
            timeout=timeout,
            chunked=True,
            read_until_eof=False,
        ) as resp:

            conn = resp.connection
            # resp._closed = True  # hijack response
            transport = conn.transport
            protocol = conn.protocol
            loop = resp._loop

            reader: FlowControlDataQueue[aiohttp.WSMessage] = FlowControlDataQueue(
                protocol, limit=2 ** 16, loop=loop
            )
            writer = _ExecWriter(transport)
            protocol.set_parser(_ExecParser(reader, tty=tty), reader)
            yield aiohttp.ClientWebSocketResponse(
                reader,
                cast(WebSocketWriter, writer),
                None,  # protocol
                resp,
                timeout,
                True,  # autoclose
                False,  # autoping
                loop,
                receive_timeout=10,
            )

    async def _start_detached(
        self, timeout: aiohttp.ClientTimeout = None, tty: bool = False,
    ) -> bytes:
        async with self.docker._query(
            f"exec/{self._id}/start",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"Detach": True, "Tty": tty}),
            timeout=timeout,
        ) as response:
            result = await response.read()
            await response.release()
            return result


Message = namedtuple("Message", "stream data")


class _ExecParser:
    def __init__(self, queue, tty=False):
        self.queue = queue
        self.tty = tty
        self._exc = None
        self.header_fmt = struct.Struct(">BxxxL")

    def feed_eof(self):
        self.queue.feed_eof()

    def feed_data(self, data):
        if self._exc:
            return True, data

        try:
            if self.tty:
                msg = Message(1, data)  # stdout
                self.queue.feed_data(msg, len(data))
            else:
                while data:
                    # Parse the header
                    if len(data) < self.header_fmt.size:
                        raise IOError("Not enough data was received to parse header.")
                    fileno, msglen = self.header_fmt.unpack(
                        data[: self.header_fmt.size]
                    )
                    msg_and_header = self.header_fmt.size + msglen
                    if len(data) < msg_and_header:
                        raise IOError(
                            "Not enough data was received to contain the payload."
                        )
                    msg = Message(
                        fileno,
                        data[self.header_fmt.size : msg_and_header],
                    )
                    self.queue.feed_data(msg, msglen)
                    data = data[msg_and_header:]
            return False, b""
        except Exception as exc:
            self._exc = exc
            self.queue.set_exception(exc)
            return True, b""


class ExecStream:
    def __init__(
        self,
        docker: 'Docker',
        exec_id: str,
        tty: bool,
        timeout: Optional[aiohttp.ClientTimeout],
    ) -> None:
        self._id = exec_id
        self.docker = docker
        self._tty = tty
        self._resp = None
        self._closed = False
        self._timeout = timeout
        self._queue = None

    async def _init(self) -> None:
        if self._resp is not None:
            return
        body = json.dumps({"Detach": False, "Tty": self._tty})
        self._resp = resp = await self.docker._do_query(
            f"exec/{self._id}/start",
            method="POST",
            data=body,
            params=None,
            headers={"Connection": "Upgrade", "Upgrade": "tcp"},
            timeout=self._timeout,
            chunked=True,
            read_until_eof=False,
        )

        conn = resp.connection
        # resp._closed = True  # hijack response
        protocol = conn.protocol
        loop = resp._loop

        queue: FlowControlDataQueue[Message] = FlowControlDataQueue(
            protocol, limit=2 ** 16, loop=loop
        )
        protocol.set_parser(_ExecParser(queue, tty=self._tty), queue)
        self._queue = queue

    async def read_out(self) -> Message:
        """Read from stdout or stderr."""
        await self._init()
        return await self._queue.read()

    async def write_in(self, data: bytes) -> None:
        """Write into stdin."""
        if self._closed:
            raise RuntimeError("Cannot write to closed transport")
        await self._init()
        transport = self._resp.connection.transport
        transport.write(data)

    async def close(self) -> None:
        if self._resp is not None:
            return
        if self._closed:
            return
        self._closed = True
        transport = self._resp.connection.transport
        transport.write_eof()
        await self._resp.close()

    async def __aenter__(self) -> "ExecStream":
        await self._init()
        return self

    async def __aexit__(
        self,
        exc_typ: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        await self.close()

    def __del__(self, _warnings=warnings) -> None:
        if self._resp is not None:
            return
        if not self._closed:
            warnings.warn("Unclosed ExecStream")
