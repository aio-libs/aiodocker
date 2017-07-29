import sys
import types
import asyncio
import json
import logging
import aiohttp

log = logging.getLogger(__name__)


class _JsonStreamResult:
    def __init__(self, response, transform=None):
        self._response = response
        self._transform = transform or (lambda x: x)

    def __aiter__(self):
        return self

    if sys.version_info <= (3, 5, 2):
        __aiter__ = asyncio.coroutine(__aiter__)

    @types.coroutine
    def __anext__(self):
        while True:
            try:
                data = yield from self._response.content.readline()
                if not data:
                    break
            except (aiohttp.ClientConnectionError,
                    aiohttp.ServerDisconnectedError):
                break
            return self._transform(json.loads(data.decode('utf8')))

        raise StopAsyncIteration

    async def _close(self):
        # response.release() indefinitely hangs because the server is sending
        # an infinite stream of messages.
        # (see https://github.com/KeepSafe/aiohttp/issues/739)

        # response error , it has been closed
        await self._response.close()


async def json_stream_result(response, transform=None, stream=True):
    json_stream = _JsonStreamResult(response, transform)

    if stream:
        return json_stream

    data = []
    async for obj in json_stream:
        data.append(obj)
    return data
