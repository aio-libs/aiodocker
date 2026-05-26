from __future__ import annotations

import json
import logging
import types
from typing import Any, Dict

import aiohttp

from .exceptions import DockerStreamError


log = logging.getLogger(__name__)


def _maybe_raise_stream_error(data: Dict[str, Any]) -> None:
    """Inspect a parsed JSON chunk and raise if it carries a Docker error.

    The Docker Engine's progress streams (``images/create`` for pull,
    ``images/{name}/push``, ``build``, ``images/load``) return HTTP 200
    and report failures as in-band JSON lines such as::

        {"errorDetail": {"message": "denied: ..."}, "error": "denied: ..."}

    When such a chunk appears, raise :class:`DockerStreamError` so callers
    don't silently treat the operation as successful.
    """
    if "errorDetail" not in data and "error" not in data:
        return
    detail = data.get("errorDetail")
    if isinstance(detail, dict):
        message = detail.get("message") or data.get("error")
        error_detail = detail
    else:
        message = data.get("error")
        error_detail = {"raw": detail} if detail is not None else {}
    if not message:
        message = "unknown error in Docker JSON stream"
    raise DockerStreamError(message, error_detail=error_detail)


class _JsonStreamResult:
    def __init__(self, response, transform=None, *, raise_on_error: bool = True):
        self._response = response
        self._transform = transform or (lambda x: x)
        self._raise_on_error = raise_on_error

    def __aiter__(self):
        return self

    @types.coroutine
    def __anext__(self):
        while True:
            try:
                data = yield from self._response.content.readline()
                if not data:
                    break
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError):
                break
            decoded = json.loads(data.decode("utf8"))
            if self._raise_on_error:
                try:
                    _maybe_raise_stream_error(decoded)
                except DockerStreamError:
                    # Release the underlying response so the connection
                    # isn't left dangling for GC to clean up. The Docker
                    # Engine typically closes the stream right after
                    # emitting the error chunk, but we can't rely on it.
                    self._response.close()
                    raise
            return self._transform(decoded)

        raise StopAsyncIteration

    async def _close(self):
        # response.release() indefinitely hangs because the server is sending
        # an infinite stream of messages.
        # (see https://github.com/KeepSafe/aiohttp/issues/739)

        # response error , it has been closed
        self._response.close()


def json_stream_stream(response, transform=None, *, raise_on_error: bool = True):
    json_stream = _JsonStreamResult(response, transform, raise_on_error=raise_on_error)
    return json_stream


async def json_stream_list(response, transform=None, *, raise_on_error: bool = True):
    json_stream = _JsonStreamResult(response, transform, raise_on_error=raise_on_error)

    data = []
    async for obj in json_stream:
        data.append(obj)
    return data
