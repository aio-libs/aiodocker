import json
import struct
import warnings
from collections import namedtuple
from types import TracebackType
from typing import TYPE_CHECKING, Optional, Type

import aiohttp


Message = namedtuple("Message", "stream data")

if TYPE_CHECKING:
    from .docker import Docker


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
                    msg = Message(fileno, data[self.header_fmt.size : msg_and_header],)
                    self.queue.feed_data(msg, msglen)
                    data = data[msg_and_header:]
            return False, b""
        except Exception as exc:
            self._exc = exc
            self.queue.set_exception(exc)
            return True, b""


class Stream:
    def __init__(
        self,
        docker: "Docker",
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

        queue: aiohttp.FlowControlDataQueue[Message] = aiohttp.FlowControlDataQueue(
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
            warnings.warn("Unclosed ExecStream")
