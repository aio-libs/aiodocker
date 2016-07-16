import struct
import asyncio
from . import constants


class MultiplexedResult(object):
    def __init__(self, response):
        self.response = response

    @asyncio.coroutine
    def __aiter__(self):
        return self

    @asyncio.coroutine
    def __anext__(self):
        while True:
            header = yield from self.response.content.read(constants.STREAM_HEADER_SIZE_BYTES)
            if not header:
                break
            _, length = struct.unpack('>BxxxL', header)
            if not length:
                continue
            data = yield from self.response.content.read(length)
            if not data:
                break
            return data
        yield from self.response.release()
        raise StopAsyncIteration
