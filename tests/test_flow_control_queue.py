"""Tests for the vendored ``FlowControlDataQueue``."""

import asyncio
from typing import cast

import pytest
from aiohttp import EofStream
from aiohttp.base_protocol import BaseProtocol

from aiodocker._flow_control_queue import FlowControlDataQueue


class _FakeProtocol:
    def __init__(self) -> None:
        self._reading_paused = False
        self.pause_calls = 0
        self.resume_calls = 0

    def pause_reading(self) -> None:
        self._reading_paused = True
        self.pause_calls += 1

    def resume_reading(self) -> None:
        self._reading_paused = False
        self.resume_calls += 1


def _make_protocol() -> BaseProtocol:
    """Return a `_FakeProtocol` typed as `BaseProtocol` for the queue constructor."""
    return cast(BaseProtocol, _FakeProtocol())


@pytest.mark.asyncio
async def test_feed_and_read_preserves_order() -> None:
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        _make_protocol(), limit=64
    )
    queue.feed_data(b"a", 1)
    queue.feed_data(b"b", 1)
    queue.feed_eof()

    assert await queue.read() == b"a"
    assert await queue.read() == b"b"
    with pytest.raises(EofStream):
        await queue.read()


@pytest.mark.asyncio
async def test_feed_data_pauses_when_limit_exceeded() -> None:
    protocol = _FakeProtocol()
    # ``FlowControlDataQueue`` doubles the supplied limit internally, so the
    # effective pause threshold is ``limit * 2 = 20``.
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        cast(BaseProtocol, protocol), limit=10
    )

    # Stays comfortably below the threshold -> never paused.
    queue.feed_data(b"hello", 5)
    assert protocol.pause_calls == 0
    assert protocol._reading_paused is False

    # Crosses the threshold -> paused exactly once.
    queue.feed_data(b"x" * 25, 25)
    assert protocol.pause_calls == 1
    assert protocol._reading_paused is True


@pytest.mark.asyncio
async def test_read_resumes_when_below_limit() -> None:
    protocol = _FakeProtocol()
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        cast(BaseProtocol, protocol), limit=10
    )

    queue.feed_data(b"hello", 5)
    queue.feed_data(b"x" * 25, 25)
    assert protocol._reading_paused is True

    # Draining the large payload drops well below the threshold -> resumed once.
    assert await queue.read() == b"hello"
    assert await queue.read() == b"x" * 25
    assert protocol.resume_calls == 1
    assert protocol._reading_paused is False


@pytest.mark.asyncio
async def test_read_waits_for_data() -> None:
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        _make_protocol(), limit=64
    )

    async def producer() -> None:
        await asyncio.sleep(0)
        queue.feed_data(b"x", 1)

    producer_task = asyncio.create_task(producer())
    result = await queue.read()
    await producer_task
    assert result == b"x"


@pytest.mark.asyncio
async def test_set_exception_propagates() -> None:
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        _make_protocol(), limit=64
    )

    queue.set_exception(RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        await queue.read()
