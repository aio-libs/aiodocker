import asyncio
import json

import aiohttp.errors


class JsonStreamResult(object):
    def __init__(self, response, transform=None):
        self.response = response
        self.transform = transform or (lambda x: x)

    @asyncio.coroutine
    def __aiter__(self):
        self._open = True
        return self

    @asyncio.coroutine
    def __anext__(self):
        while self._open:
            try:
                data = yield from self.response.content.readline()
            except aiohttp.errors.ClientDisconnectedError:
                data = None
            if not data:
                self._open = False
                break
            return self.transform(json.loads(data.decode('utf8')))

        yield from self.response.release()
        raise StopAsyncIteration

    def close(self):
        self.response.close()
