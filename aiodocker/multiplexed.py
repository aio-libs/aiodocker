import asyncio
import struct
import aiohttp

from . import constants
from aiodocker.utils import decoded


class MultiplexedResult:
    def __init__(self, response):
        self.response = response

    async def fetch(self):
        try:
            while True:
                try:
                    hdrlen = constants.STREAM_HEADER_SIZE_BYTES
                    header = await self.response.content.readexactly(hdrlen)
                    _, length = struct.unpack('>BxxxL', header)
                    if not length:
                        continue
                    data = await self.response.content.readexactly(length)
                except (aiohttp.ClientConnectionError,
                        aiohttp.ServerDisconnectedError):
                    break
                except asyncio.IncompleteReadError:
                    break
                yield data
        finally:
            await self.close()

    async def fetch_raw(self):
        try:
            async for data in self.response.content.iter_chunked(1024):
                yield data
        finally:
            await self.close()

    async def close(self):
        await self.response.release()


async def multiplexed_result(response, follow=False, is_tty=False,
                             encoding='utf-8'):
    log_stream = MultiplexedResult(response)

    if is_tty:
        if follow:
            return decoded(log_stream.fetch_raw(), encoding=encoding)
        else:
            d = []
            async for piece in decoded(log_stream.fetch_raw(),
                                       encoding=encoding):
                d.append(piece)
            return ''.join(d)
    else:
        if follow:
            return decoded(log_stream.fetch(), encoding=encoding)
        else:
            d = []
            async for piece in decoded(log_stream.fetch(),
                                       encoding=encoding):
                d.append(piece)
            return ''.join(d)
