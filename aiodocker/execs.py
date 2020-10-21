import json
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, overload

import aiohttp
from typing_extensions import Literal
from yarl import URL

from .stream import Stream


if TYPE_CHECKING:
    from .docker import Docker


# When a Tty is allocated for an "exec" operation, the stdout and stderr are streamed
# straight to the client.
# When a Tty is NOT allocated, then stdout and stderr are multiplexed using the format
# given at
# https://docs.docker.com/engine/api/v1.40/#operation/ContainerAttach under the "Stream
# Format" heading. Note that that documentation is for "docker attach" but the format
# also applies to "docker exec."


class Exec:
    def __init__(self, docker: "Docker", id: str, tty: Optional[bool]) -> None:
        self.docker = docker
        self._id = id
        self._tty = tty

    @property
    def id(self) -> str:
        return self._id

    async def inspect(self) -> Dict[str, Any]:
        ret = await self.docker._query_json(f"exec/{self._id}/json")
        self._tty = ret["ProcessConfig"]["tty"]
        return ret

    async def resize(self, *, h: Optional[int] = None, w: Optional[int] = None) -> None:
        dct: Dict[str, int] = {}
        if h is not None:
            dct["h"] = h
        if w is not None:
            dct["w"] = w
        if not dct:
            return
        url = URL(f"exec/{self._id}/resize").with_query(dct)
        async with self.docker._query(url, method="POST") as resp:
            resp

    @overload
    def start(
        self,
        *,
        timeout: aiohttp.ClientTimeout = None,
        detach: Literal[False] = False,
    ) -> Stream:
        pass

    @overload  # noqa
    async def start(
        self,
        *,
        timeout: aiohttp.ClientTimeout = None,
        detach: Literal[True],
    ) -> bytes:
        pass

    def start(self, *, timeout=None, detach=False):  # noqa
        """
        Start this exec instance.
        Args:
            timeout: The timeout in seconds for the request to start the exec instance.
            detach: Indicates whether we should detach from the command (like the `-d`
                option to `docker exec`).
            tty: Indicates whether a TTY should be allocated (like the `-t` option to
                `docker exec`).
        Returns:
            If `detach` is `True`, this method will return the result of the exec
            process as a binary string.
            If `detach` is False, an `aiohttp.ClientWebSocketResponse` will be returned.
            You can use it to send and receive data the same wa as the response of
            "ws_connect" of aiohttp. If `tty` is `False`, then the messages returned
            from `receive*` will have their `extra` attribute set to 1 if the data was
            from stdout or 2 if from stderr.
        """
        if detach:
            return self._start_detached(timeout, self._tty)
        else:

            async def setup() -> Tuple[URL, bytes, bool]:
                if self._tty is None:
                    await self.inspect()  # should restore tty
                assert self._tty is not None
                return (
                    URL(f"exec/{self._id}/start"),
                    json.dumps({"Detach": False, "Tty": self._tty}).encode("utf8"),
                    self._tty,
                )

            return Stream(self.docker, setup, timeout)

    async def _start_detached(
        self,
        timeout: aiohttp.ClientTimeout = None,
        tty: bool = False,
    ) -> bytes:
        if self._tty is None:
            await self.inspect()  # should restore tty
        assert self._tty is not None
        async with self.docker._query(
            f"exec/{self._id}/start",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"Detach": True, "Tty": tty}),
            timeout=timeout,
        ) as response:
            result = await response.read()
            await response.release()
            return result
