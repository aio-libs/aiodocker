import asyncio


class StreamReader:
    def __init__(self, response):
        self._response = response

    @asyncio.coroutine
    def read(self, n=-1):
        return (yield from self._response.content.read(n))

    @asyncio.coroutine
    def readany(self):
        return (yield from self._response.content.readany())

    @asyncio.coroutine
    def readexactly(self, n):
        return (yield from self._response.content.readexactly(n))

    @asyncio.coroutine
    def readline(self):
        return (yield from self._response.content.readline())

    @asyncio.coroutine
    def release(self):
        yield from self._response.release()

    def close(self):
        self._response.close()

    def at_eof(self):
        self._response.content.at_eof()

    @property
    def response(self):
        return self._response
