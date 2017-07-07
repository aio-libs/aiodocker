import sys
import asyncio
import struct
import aiohttp

from . import constants
from aiodocker.utils import _DecodeHelper


class MultiplexedResult:
    def __init__(self, response, raw):
        self._response = response

        if raw:
            self._iter = self.fetch_raw
        else:
            self._iter = self.fetch

    def __aiter__(self):
        return self

    if sys.version_info <= (3, 5, 2):
        __aiter__ = asyncio.coroutine(__aiter__)

    async def __anext__(self):
        response = await self._iter()
        if not response:
            raise StopAsyncIteration
        return response

    async def fetch(self):
        try:
            while True:
                try:
                    hdrlen = constants.STREAM_HEADER_SIZE_BYTES
                    header = await self._response.content.readexactly(hdrlen)
                    _, length = struct.unpack('>BxxxL', header)
                    if not length:
                        continue
                    data = await self._response.content.readexactly(length)
                except (aiohttp.ClientConnectionError,
                        aiohttp.ServerDisconnectedError):
                    break
                except asyncio.IncompleteReadError:
                    break
                return data
        finally:
            await self.close()

    async def fetch_raw(self):
        try:
            async for data in self._response.content.iter_chunked(1024):
                return data
        except aiohttp.ClientConnectionError:
            pass
        finally:
            await self.close()

    async def close(self):
        await self._response.release()


async def multiplexed_result(response, follow=False, is_tty=False,
                             encoding='utf-8'):

    log_stream = MultiplexedResult(response, raw=False)
    if is_tty:
        log_stream = MultiplexedResult(response, raw=True)

    if follow:
        return _DecodeHelper(log_stream, encoding=encoding)
    else:
        d = []
        async for piece in _DecodeHelper(log_stream, encoding=encoding):
            if isinstance(piece, str):
                d.append(piece)
        return ''.join(d)
