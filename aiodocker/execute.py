import json
import struct
from typing import cast, Any, Dict, List, Optional, TYPE_CHECKING, Union

from aiohttp import ClientWebSocketResponse, WSMessage, WSMsgType, FlowControlDataQueue
from aiohttp.http_websocket import WebSocketWriter

if TYPE_CHECKING:
    from .containers import DockerContainer

# When a Tty is allocated for an "exec" operation, the stdout and stderr are streamed
# straight to the client.
# When a Tty is NOT allocated, then stdout and stderr are multiplexed using the format
# given at
# https://docs.docker.com/engine/api/v1.40/#operation/ContainerAttach under the "Stream
# Format" heading. Note that that documentation is for "docker attach" but the format
# also applies to "docker exec."

STDOUT = 1
STDERR = 2


class ExecReader:
    def __init__(self, queue, tty=False):
        self.queue = queue
        self.tty = tty
        self._exc = None
        self.header_fmt = struct.Struct(">BxxxL")

    def feed_eof(self):
        self.queue.feed_eof()

    def feed_data(self, data):
        if self._exc:
            return True, data

        try:
            # Wrap with WSMessage to deceive ClientWebSocketResponse
            if self.tty:
                msg = WSMessage(WSMsgType.BINARY, data, STDOUT)
                self.queue.feed_data(msg, len(data))
            else:
                while data:
                    # Parse the header
                    if len(data) < self.header_fmt.size:
                        raise IOError("Not enough data was received to parse header.")
                    fileno, msglen = self.header_fmt.unpack(
                        data[: self.header_fmt.size]
                    )
                    msg_and_header = self.header_fmt.size + msglen
                    if len(data) < msg_and_header:
                        raise IOError(
                            "Not enough data was received to contain the payload."
                        )
                    msg = WSMessage(
                        WSMsgType.BINARY,
                        data[self.header_fmt.size:msg_and_header],
                        fileno,
                    )
                    self.queue.feed_data(msg, msglen)
                    data = data[msg_and_header:]
            return False, b""
        except Exception as exc:
            self._exc = exc
            self.queue.set_exception(exc)
            return True, b""


class ExecWriter:
    def __init__(self, transport):
        self.transport = transport

    async def send(self, message, *args, **kwargs):
        if isinstance(message, str):
            message = message.encode("utf-8")
        self.transport.write(message)

    def write_eof(self):
        self.transport.write_eof()

    async def close(self, code=1000, message=b""):
        self.write_eof()
        return None


class Exec:
    def __init__(self, exec_id, container):
        self.exec_id = exec_id
        self.container = container

    @classmethod
    async def create(
        cls,
        container,  # type: DockerContainer
        AttachStdin: Optional[bool] = None,
        AttachStdout: Optional[bool] = None,
        AttachStderr: Optional[bool] = None,
        DetachKeys: Optional[str] = None,
        Tty: Optional[bool] = None,
        Env: Optional[List[str]] = None,
        Cmd: Union[None, str, List[str]] = None,
        Privileged: Optional[bool] = None,
        User: Optional[str] = None,
        WorkingDir: Optional[str] = None,
    ) -> "Exec":
        """ Create and return an instance of Exec. See
        https://docs.docker.com/engine/api/v1.40/#operation/ContainerExec for
        information on the available parameters.
        """
        kwargs = {}
        for name in (
            "AttachStdin",
            "AttachStdout",
            "AttachStderr",
            "DetachKeys",
            "Tty",
            "Env",
            "Cmd",
            "Privileged",
            "User",
            "WorkingDir",
        ):
            val = locals()[name]
            if val is not None:
                kwargs[name] = val
        data = await container.docker._query_json(
            "containers/{container._id}/exec".format(container=container),
            method="POST",
            data=kwargs,
        )
        return cls(data["Id"], container)

    async def start(
        self,
        timeout: int = 10,
        receive_timeout: Optional[int] = None,
        Detach: bool = False,
        Tty: bool = False,
    ) -> Union[ClientWebSocketResponse, bytes]:
        """
        Start this exec instance.

        Args:
            timeout: The timeout in seconds for the request to start the exec instance.
            receive_timeout: The timeout in seconds that will be allowing when
                attempting to read from the output stream of the instance.
            Detach: Indicates whether we should detach from the command (like the `-d`
                option to `docker exec`).
            Tty: Indicates whether a TTY should be allocated (like the `-t` option to
                `docker exec`).

        Returns:
            If `Detach` is `True`, this method will return the result of the exec
            process as a binary string.
            If `Detach` is False, an `aiohttp.ClientWebSocketResponse` will be returned.
            You can use it to send and receive data the same wa as the response of
            "ws_connect" of aiohttp. If `Tty` is `False`, then the messages returned
            from `receive*` will have their `extra` attribute set to 1 if the data was
            from stdout or 2 if from stderr.
        """
        # Don't use docker._query_json
        # content-type of response will be "vnd.docker.raw-stream",
        # so it will cause error.
        response = await self.container.docker._query(
            "exec/{exec_id}/start".format(exec_id=self.exec_id),
            method="POST",
            headers={
                "content-type": "application/json",
                "Connection": "Upgrade",
                "Upgrade": "TCP",
            },
            data=json.dumps({"Detach": Detach, "Tty": Tty}),
            read_until_eof=Detach,
            timeout=timeout,
        )

        if not Detach:
            conn = response.connection
            transport = conn.transport
            protocol = conn.protocol
            loop = response._loop

            reader = FlowControlDataQueue(
                protocol, limit=2 ** 16, loop=loop
            )  # type: FlowControlDataQueue[WSMessage]
            writer = ExecWriter(transport)
            protocol.set_parser(ExecReader(reader, tty=Tty), reader)
            return ClientWebSocketResponse(
                reader,
                cast(WebSocketWriter, writer),
                None,  # protocol
                response,
                timeout,
                True,  # autoclose
                False,  # autoping
                loop,
                receive_timeout=receive_timeout,
            )

        else:
            result = await response.read()
            await response.release()
            return result

    async def resize(self, h: Optional[int] = None, w: Optional[int] = None):
        """ Resize the size of the TTY being used for the exec instance.

        Args:
            h: The desired height of the TTY in characters.
            w: The desired width of the TTY in characters.
        """
        kwargs = {}
        if h is not None:
            kwargs["h"] = h
        if w is not None:
            kwargs["w"] = w
        await self.container.docker._query(
            "exec/{exec_id}/resize".format(exec_id=self.exec_id),
            method="POST",
            params=kwargs,
        )

    async def inspect(self) -> Dict[str, Any]:
        """ Return low-level information about an exec instance. """
        data = await self.container.docker._query_json(
            "exec/{exec_id}/json".format(exec_id=self.exec_id), method="GET"
        )
        return data
