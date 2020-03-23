import socket
import struct
import warnings
from collections import namedtuple
from types import TracebackType
from typing import TYPE_CHECKING, Awaitable, Callable, Optional, Tuple, Type

import aiohttp
from yarl import URL


if TYPE_CHECKING:
    from .docker import Docker

Message = namedtuple("Message", "stream data")


class Stream:
    def __init__(
        self,
        docker: "Docker",
        setup: Callable[[], Awaitable[Tuple[URL, bytes, bool]]],
        timeout: Optional[aiohttp.ClientTimeout],
    ) -> None:
        self._setup = setup
        self.docker = docker
        self._resp = None
        self._closed = False
        self._timeout = timeout
        self._queue = None

    async def _init(self) -> None:
        if self._resp is not None:
            return
        url, body, tty = await self._setup()
        timeout = self._timeout
        if timeout is None:
            # total timeout doesn't make sense for streaming
            timeout = aiohttp.ClientTimeout()
        self._resp = resp = await self.docker._do_query(
            url,
            method="POST",
            data=body,
            params=None,
            headers={"Connection": "Upgrade", "Upgrade": "tcp"},
            timeout=timeout,
            chunked=None,
            read_until_eof=False,
        )
        await resp.read()  # skip empty body

        conn = resp.connection
        protocol = conn.protocol
        loop = resp._loop
        sock = protocol.transport.get_extra_info("socket")
        if sock is not None:
            # set TCP keepalive for vendored socket
            # the socket can be closed in the case of error
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        queue: aiohttp.FlowControlDataQueue[Message] = aiohttp.FlowControlDataQueue(
            protocol, limit=2 ** 16, loop=loop
        )
        protocol.set_parser(_ExecParser(queue, tty=tty), queue)
        protocol.force_close()
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

    async def __aenter__(self) -> "Stream":
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
            warnings.warn("Unclosed ExecStream", ResourceWarning)


class _ExecParser:
    def __init__(self, queue, tty=False):
        self.queue = queue
        self.tty = tty
        self.header_fmt = struct.Struct(">BxxxL")
        self._buf = bytearray()

    def feed_eof(self):
        self.queue.feed_eof()

    def feed_data(self, data):
        if self.tty:
            msg = Message(1, data)  # stdout
            self.queue.feed_data(msg, len(data))
        else:
            self._buf.extend(data)
            while self._buf:
                # Parse the header
                if len(self._buf) < self.header_fmt.size:
                    return False, ""
                fileno, msglen = self.header_fmt.unpack(
                    self._buf[: self.header_fmt.size]
                )
                msg_and_header = self.header_fmt.size + msglen
                if len(self._buf) < msg_and_header:
                    return False, ""
                msg = Message(
                    fileno, bytes(self._buf[self.header_fmt.size : msg_and_header])
                )
                self.queue.feed_data(msg, msglen)
                del self._buf[:msg_and_header]
        return False, b""
