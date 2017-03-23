import asyncio
import struct
import aiohttp

from . import constants

# aiohttp has no errors.py
try:
    import aiohttp.errors as errors
except:
    import aiohttp.client_exceptions as errors


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
                #except (aiohttp.errors.ClientDisconnectedError,
                #        aiohttp.errors.ServerDisconnectedError):
                except errors.ServerDisconnectedError:
                    break
                except asyncio.IncompleteReadError:
                    break
                yield data.decode('utf8')
        finally:

            await self.close()

    async def fetch_raw(self):
        try:
            async for data in self.response.content.iter_chunked(1024):
                yield data.decode('utf8')
        finally:

            await self.close()

    async def close(self):

        if self.response.release():
            await self.response.release()


async def multiplexed_result(response, follow=False, isTty=False):
    log_stream = MultiplexedResult(response)

    if isTty:
        if follow:
            return log_stream.fetch_raw()
        else:
            d = ''
            async for l in log_stream.fetch_raw():
                d = d + l

            return d
    else:
        if follow:
            return log_stream.fetch()
        else:
            d = ''
            async for l in log_stream.fetch():
                d = d + l

            return d

#    data = []
#    async for record in log_stream.fetch():
#        data.append(record)
#    return data
