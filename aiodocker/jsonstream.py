import json
import logging
import aiohttp

log = logging.getLogger(__name__)


class JsonStreamResult:
    def __init__(self, response, transform=None):
        self.response = response
        self.transform = transform or (lambda x: x)

    async def fetch(self):
        while True:
            try:
                data = await self.response.content.readline()
                if not data:
                    break
            except (aiohttp.ClientConnectionError,
                   aiohttp.ServerDisconnectedError):
                break
            yield self.transform(json.loads(data.decode('utf8')))

    async def close(self):
        # response.release() indefinitely hangs because the server is sending
        # an infinite stream of messages.
        # (see https://github.com/KeepSafe/aiohttp/issues/739)

        # response error , it has been closed
        if self.response.close():
            await self.response.close()


async def json_stream_result(response, transform=None, stream=True):
    json_stream = JsonStreamResult(response, transform)
    if stream:
        return json_stream
    data = []
    async for obj in json_stream.fetch():
        data.append(obj)
    return data
