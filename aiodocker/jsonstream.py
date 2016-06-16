import asyncio
import json


class JsonStreamResult(object):
    def __init__(self, response):
        self.response = response


    @asyncio.coroutine
    def __aiter__(self):
        self._buff = ''
        self._open = True
        return self

    @asyncio.coroutine
    def __anext__(self):
        chunk_size = 20
        while self._open:
            if '\r\n' in self._buff:
                json_line, self._buff = self._buff.split('\r\n', 1)
                return json.loads(json_line)
            data = yield from self.response.content.read(chunk_size)
            if not data:
                self._open = False
                if self._buff:
                    return json.loads(self._buff)
                break
            self._buff += data.decode('utf8')

        yield from self.response.release()
        raise StopAsyncIteration
