import sys
import types
import asyncio
import struct
import aiohttp

from . import constants
from aiodocker.utils import _DecodeHelper


class MultiplexedResult:
    def __init__(self, response, raw):
        self._response = response

        self._gen = self.fetch
        if raw:
            self._gen = self.fetch_raw

    def __aiter__(self):
        return self

    async def __anext__(self):
        response = await self._gen()

        if not response:
            await self._close()
            raise StopAsyncIteration

        return response

    if sys.version_info <= (3, 5, 2):
        __aiter__ = asyncio.coroutine(__aiter__)

    @types.coroutine
    def fetch(self):
        while True:

            try:
                hdrlen = constants.STREAM_HEADER_SIZE_BYTES
                header = yield from self._response.content.readexactly(hdrlen)

                _, length = struct.unpack('>BxxxL', header)
                if not length:
                    continue

                data = yield from self._response.content.readexactly(length)

            except (aiohttp.ClientConnectionError,
                    aiohttp.ServerDisconnectedError,
                    asyncio.IncompleteReadError):
                break
            return data

    @types.coroutine
    def fetch_raw(self):
        chunk = self._response.content.iter_chunked(1024).__aiter__()
        while True:
            try:
                data = yield from chunk.__anext__()
            except StopAsyncIteration:
                break
            return data

    async def _close(self):
        await self._response.release()


async def multiplexed_result(response, follow=False, is_tty=False,
                             encoding='utf-8'):

    # if is_tty is True you get a raw output
    log_stream = MultiplexedResult(response, raw=is_tty)

    if follow:
        return _DecodeHelper(log_stream, encoding=encoding)
    else:
        d = []
        async for piece in _DecodeHelper(log_stream, encoding=encoding):
            d.append(piece.strip())
        return d
