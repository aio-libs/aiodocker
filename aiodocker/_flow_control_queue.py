"""Vendored copy of aiohttp's ``FlowControlDataQueue``.

Vendored from aiohttp 3.11/3.13 since the class is deprecated and will be
removed in aiohttp 4.0. See https://github.com/aio-libs/aiodocker/issues/919
and https://github.com/aio-libs/aiohttp/pull/9963.

This implementation tracks payload sizes locally instead of relying on
``DataQueue._size``, which is private and whose presence varies across the
``aiohttp>=3.10,<4.0`` range (3.10 maintains it, 3.13 dropped it). Composing
around ``super().feed_data()`` / ``super().read()`` keeps the class working
identically on every supported aiohttp version.
"""

from __future__ import annotations

import asyncio
import collections
from typing import Deque, TypeVar

from aiohttp import DataQueue
from aiohttp.base_protocol import BaseProtocol


_T = TypeVar("_T")


class FlowControlDataQueue(DataQueue[_T]):
    """FlowControlDataQueue resumes and pauses an underlying stream.

    It is a destination for parsed data.
    """

    def __init__(self, protocol: BaseProtocol, limit: int) -> None:
        super().__init__(loop=asyncio.get_running_loop())
        self._protocol = protocol
        self._limit = limit * 2
        self._flow_size = 0
        self._flow_sizes: Deque[int] = collections.deque()

    def feed_data(self, data: _T, size: int = 0) -> None:
        super().feed_data(data, size)
        self._flow_size += size
        self._flow_sizes.append(size)

        if self._flow_size > self._limit and not self._protocol._reading_paused:
            self._protocol.pause_reading()

    async def read(self) -> _T:
        data = await super().read()
        if self._flow_sizes:
            self._flow_size -= self._flow_sizes.popleft()
        if self._flow_size < self._limit and self._protocol._reading_paused:
            self._protocol.resume_reading()
        return data
