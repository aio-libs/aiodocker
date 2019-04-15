import asyncio
import json

import async_timeout
from aiohttp.client_exceptions import ClientError
from aiohttp.helpers import set_result
from aiohttp.streams import EofStream, FlowControlDataQueue


class ExecReader:
    def __init__(self, queue):
        self.queue = queue
        self._exc = None

    def feed_eof(self):
        self.queue.feed_eof()

    def feed_data(self, data):
        if self._exc:
            return True, data

        try:
            self.queue.feed_data(data, len(data))
            return False, b''
        except Exception as exc:
            self._exc = exc
            self.queue.set_exception(exc)
            return True, b''


class ExecStreamResponse:
    def __init__(self, response):
        conn = response.connection
        transport = conn.transport
        protocol = conn.protocol
        loop = response._loop

        reader = FlowControlDataQueue(protocol, limit=2 ** 16, loop=loop)
        protocol.set_parser(ExecReader(reader), reader)

        self._reader = reader
        self._transport = transport
        self._response = response
        self._loop = loop
        self._closed = False
        self._waiting = None

    @property
    def closed(self):
        return self._closed

    def send_bytes(self, data):
        self._transport.write(data)

    def send_str(self, data):
        msg = data.encode('utf-8')
        self.send_bytes(msg)

    async def close(self):
        if self._waiting is not None and not self._closed:
            await self._waiting
        if self._closed:
            return False

        self._closed = True
        self._response.close()
        return True

    async def receive(self, timeout=None):
        while True:
            try:
                self._waiting = self._loop.create_future()

                try:
                    with async_timeout.timeout(timeout, loop=self._loop):
                        msg = await self._reader.read()
                finally:
                    waiter = self._waiting
                    self._waiting = None
                    set_result(waiter, True)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                raise
            except EofStream:
                await self.close()
                return
            except ClientError:
                self._closed = True
                return
            except Exception:
                await self.close()
                raise

            return msg

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self.receive()
        if msg is None:
            raise StopAsyncIteration
        return msg

    def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


class Exec:
    def __init__(self, exec_id, container):
        self.exec_id = exec_id
        self.container = container

    @classmethod
    async def create(cls, container, **kwargs):
        data = await container.docker._query_json(
            "containers/{container._id}/exec".format(container=container),
            method='POST', data=kwargs,
        )
        return cls(data["Id"], container)

    async def start(self, stream=False, **kwargs):
        # Don't use docker._query_json
        # content-type of response will be "vnd.docker.raw-stream",
        # so it will cause error.
        response = await self.container.docker._query(
            "exec/{exec_id}/start".format(exec_id=self.exec_id),
            method='POST',
            headers={"content-type": "application/json"},
            data=json.dumps(kwargs),
            read_until_eof=not stream,
        )

        if stream:
            return ExecStreamResponse(response)
        else:
            result = await response.read()
            await response.release()
            return result

    async def resize(self, **kwargs):
        await self.container.docker._query(
            "exec/{exec_id}/resize".format(exec_id=self.exec_id), method='POST',
            params=kwargs,
        )

    async def inspect(self):
        data = await self.container.docker._query_json(
            "exec/{exec_id}/json".format(exec_id=self.exec_id), method='GET',
        )
        return data
