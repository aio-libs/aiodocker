from __future__ import annotations

import json
from typing import Iterable, List

import pytest

from aiodocker.exceptions import DockerError, DockerStreamError
from aiodocker.jsonstream import (
    _maybe_raise_stream_error,
    json_stream_list,
    json_stream_stream,
)


class _FakeContent:
    def __init__(self, lines: Iterable[bytes]) -> None:
        self._lines: List[bytes] = list(lines)

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _FakeResponse:
    def __init__(self, chunks: Iterable[dict]) -> None:
        lines = [json.dumps(chunk).encode("utf8") + b"\n" for chunk in chunks]
        self.content = _FakeContent(lines)
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_json_stream_list_collects_chunks() -> None:
    response = _FakeResponse([{"status": "Pulling"}, {"status": "Pull complete"}])
    result = await json_stream_list(response)
    assert result == [{"status": "Pulling"}, {"status": "Pull complete"}]


@pytest.mark.asyncio
async def test_json_stream_list_raises_on_error_detail() -> None:
    response = _FakeResponse([
        {"status": "The push refers to repository [registry/foo]"},
        {
            "errorDetail": {"message": "denied: not authorized"},
            "error": "denied: not authorized",
        },
    ])
    with pytest.raises(DockerStreamError) as excinfo:
        await json_stream_list(response)
    assert "denied: not authorized" in excinfo.value.message
    assert excinfo.value.error_detail == {"message": "denied: not authorized"}


@pytest.mark.asyncio
async def test_json_stream_list_raises_on_bare_error_key() -> None:
    response = _FakeResponse([{"error": "something went wrong"}])
    with pytest.raises(DockerStreamError) as excinfo:
        await json_stream_list(response)
    assert excinfo.value.message == "something went wrong"
    assert excinfo.value.error_detail == {}


@pytest.mark.asyncio
async def test_json_stream_list_handles_non_dict_error_detail() -> None:
    response = _FakeResponse([{"errorDetail": "raw string", "error": "boom"}])
    with pytest.raises(DockerStreamError) as excinfo:
        await json_stream_list(response)
    assert excinfo.value.message == "boom"
    assert excinfo.value.error_detail == {"raw": "raw string"}


@pytest.mark.asyncio
async def test_json_stream_list_fallback_message_when_missing() -> None:
    response = _FakeResponse([{"errorDetail": {}}])
    with pytest.raises(DockerStreamError) as excinfo:
        await json_stream_list(response)
    assert "unknown error" in excinfo.value.message


@pytest.mark.asyncio
async def test_raise_on_error_false_passes_error_chunk_through() -> None:
    response = _FakeResponse([
        {"status": "ok"},
        {"errorDetail": {"message": "ignored"}, "error": "ignored"},
    ])
    result = await json_stream_list(response, raise_on_error=False)
    assert result == [
        {"status": "ok"},
        {"errorDetail": {"message": "ignored"}, "error": "ignored"},
    ]


@pytest.mark.asyncio
async def test_json_stream_stream_yields_progress_then_raises() -> None:
    response = _FakeResponse([
        {"status": "Pushing layer 1"},
        {"status": "Pushing layer 2"},
        {"errorDetail": {"message": "denied"}, "error": "denied"},
        {"status": "should never reach"},
    ])
    collected: List[dict] = []
    with pytest.raises(DockerStreamError) as excinfo:
        async for item in json_stream_stream(response):
            collected.append(item)
    assert collected == [
        {"status": "Pushing layer 1"},
        {"status": "Pushing layer 2"},
    ]
    assert excinfo.value.message == "denied"


@pytest.mark.asyncio
async def test_json_stream_stream_with_transform() -> None:
    response = _FakeResponse([{"value": 1}, {"value": 2}])
    collected = []
    async for item in json_stream_stream(response, lambda d: d["value"] * 10):
        collected.append(item)
    assert collected == [10, 20]


def test_docker_stream_error_is_docker_error() -> None:
    err = DockerStreamError("denied", error_detail={"message": "denied"})
    assert isinstance(err, DockerError)
    assert err.status == 0
    assert err.message == "denied"
    assert err.error_detail == {"message": "denied"}
    # Repr should mention class name and error_detail.
    assert "DockerStreamError" in repr(err)
    assert "error_detail" in repr(err)


@pytest.mark.asyncio
async def test_response_closed_when_stream_error_raised_in_list() -> None:
    response = _FakeResponse([
        {"errorDetail": {"message": "denied"}, "error": "denied"}
    ])
    with pytest.raises(DockerStreamError):
        await json_stream_list(response)
    assert response.closed is True


@pytest.mark.asyncio
async def test_response_closed_when_stream_error_raised_in_stream() -> None:
    response = _FakeResponse([
        {"status": "progress"},
        {"errorDetail": {"message": "denied"}, "error": "denied"},
    ])
    with pytest.raises(DockerStreamError):
        async for _ in json_stream_stream(response):
            pass
    assert response.closed is True


@pytest.mark.asyncio
async def test_response_not_closed_on_clean_stream() -> None:
    response = _FakeResponse([{"status": "ok"}])
    await json_stream_list(response)
    # We don't proactively close on clean exit — the surrounding
    # `async with cm as response` is responsible for that.
    assert response.closed is False


def test_maybe_raise_stream_error_no_error_keys_is_noop() -> None:
    # Should not raise for chunks without error/errorDetail.
    _maybe_raise_stream_error({"status": "Pulling"})
    _maybe_raise_stream_error({"stream": "Step 1/2"})
    _maybe_raise_stream_error({})
