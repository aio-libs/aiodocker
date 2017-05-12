import asyncio
import struct
import aiohttp
import codecs

from . import constants


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
                yield data.decode('utf8')
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


async def multiplexed_result(response, follow=False, is_tty=False):
    log_stream = MultiplexedResult(response)

    if is_tty:
        if follow:
            async def decode_wrapper(g):
                decoder = codecs.getincrementaldecoder('utf-8')(errors='ignore')
                async for d in g:
                    yield decoder.decode(d)

                d = decoder.decode(b'', final=True)
                if d:
                    yield d

            return decode_wrapper(log_stream.fetch_raw())
        else:
            d = []
            decoder = codecs.getincrementaldecoder('utf-8')(errors='ignore')
            async for l in log_stream.fetch_raw():
                s = decoder.decode(l)
                d.append(s)

            s = decoder.decode(b'', final=True)
            if s:
                d.append(s)
            return ''.join(d)
    else:
        if follow:
            return log_stream.fetch()
        else:
            d = []
            async for l in log_stream.fetch():
                d.append(l)

            return ''.join(d)
