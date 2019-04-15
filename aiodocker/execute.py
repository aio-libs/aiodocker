import asyncio
import json

import async_timeout
from aiohttp.client_exceptions import ClientError
from aiohttp.client_ws import ClientWebSocketResponse
from aiohttp.helpers import set_result
from aiohttp.http_websocket import WSMessage, WSMsgType
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
            # Wrap with WSMessage to deceive ClientWebSocketResponse
            msg = WSMessage(WSMsgType.BINARY, data, '')
            self.queue.feed_data(msg, len(data))
            return False, b''
        except Exception as exc:
            self._exc = exc
            self.queue.set_exception(exc)
            return True, b''


class ExecWriter:
    def __init__(self, transport):
        self.transport = transport

    async def send(self, message, *args, **kwargs):
        if isinstance(message, str):
            message = message.encode('utf-8')
        self.transport.write(message)

    async def close(self, code=1000, message=b''):
        return None


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

    async def start(self, stream=False, timeout=None, receive_timeout=None, **kwargs):
        # Don't use docker._query_json
        # content-type of response will be "vnd.docker.raw-stream",
        # so it will cause error.
        response = await self.container.docker._query(
            "exec/{exec_id}/start".format(exec_id=self.exec_id),
            method='POST',
            headers={"content-type": "application/json"},
            data=json.dumps(kwargs),
            read_until_eof=not stream,
            timeout=timeout,
        )

        if stream:
            conn = response.connection
            transport = conn.transport
            protocol = conn.protocol
            loop = response._loop

            reader = FlowControlDataQueue(protocol, limit=2 ** 16, loop=loop)
            writer = ExecWriter(transport)
            protocol.set_parser(ExecReader(reader), reader)
            return ClientWebSocketResponse(
                reader,
                writer,
                None,  # protocol
                response,
                timeout,
                True,  # autoclose
                False,  # autoping
                loop,
                receive_timeout=receive_timeout)

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
