import asyncio
import struct

import aiohttp

from . import constants


class MultiplexedResult:
    def __init__(self, response):
        self.response = response

    async def fetch(self):
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
            yield data.decode('utf8')

    async def close(self):
        await self.response.release()


async def multiplexed_result(response, follow=False):
    log_stream = MultiplexedResult(response)
    if follow:
        return log_stream
    data = []
    async for record in log_stream.fetch():
        data.append(record)
    return data
