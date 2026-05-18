"""Vendored copy of aiohttp's ``FlowControlDataQueue``.

Vendored from aiohttp 3.11/3.13 since the class is deprecated and will be
removed in aiohttp 4.0. See https://github.com/aio-libs/aiodocker/issues/919
and https://github.com/aio-libs/aiohttp/pull/9963.
"""

from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

from aiohttp import DataQueue, EofStream
from aiohttp.base_protocol import BaseProtocol


_T = TypeVar("_T")


class FlowControlDataQueue(DataQueue[_T], Generic[_T]):
    """FlowControlDataQueue resumes and pauses an underlying stream.

    It is a destination for parsed data.
    """

    def __init__(
        self, protocol: BaseProtocol, limit: int, *, loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__(loop=loop)
        self._size = 0
        self._protocol = protocol
        self._limit = limit * 2

    def feed_data(self, data: _T, size: int = 0) -> None:
        super().feed_data(data, size)
        self._size += size

        if self._size > self._limit and not self._protocol._reading_paused:
            self._protocol.pause_reading()

    async def read(self) -> _T:
        if not self._buffer and not self._eof:
            assert not self._waiter
            self._waiter = self._loop.create_future()
            try:
                await self._waiter
            except (asyncio.CancelledError, asyncio.TimeoutError):
                self._waiter = None
                raise
        if self._buffer:
            data, size = self._buffer.popleft()
            self._size -= size
            if self._size < self._limit and self._protocol._reading_paused:
                self._protocol.resume_reading()
            return data
        if self._exception is not None:
            raise self._exception
        raise EofStream
