"""Tests for the vendored ``FlowControlDataQueue``."""

import asyncio

import pytest
from aiohttp import EofStream

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


@pytest.mark.asyncio
async def test_feed_and_read_preserves_order() -> None:
    loop = asyncio.get_running_loop()
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        _FakeProtocol(), limit=64, loop=loop
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
    loop = asyncio.get_running_loop()
    protocol = _FakeProtocol()
    # ``FlowControlDataQueue`` doubles the limit internally, so feeding 5 +
    # 6 bytes (=11) crosses the effective threshold of 10 once.
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        protocol, limit=5, loop=loop
    )

    queue.feed_data(b"hello", 5)
    assert protocol.pause_calls == 0
    assert protocol._reading_paused is False

    queue.feed_data(b"world!", 6)
    assert protocol.pause_calls == 1
    assert protocol._reading_paused is True


@pytest.mark.asyncio
async def test_read_resumes_when_below_limit() -> None:
    loop = asyncio.get_running_loop()
    protocol = _FakeProtocol()
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        protocol, limit=5, loop=loop
    )

    queue.feed_data(b"hello", 5)
    queue.feed_data(b"world!", 6)
    assert protocol._reading_paused is True

    assert await queue.read() == b"hello"
    assert protocol.resume_calls == 1
    assert protocol._reading_paused is False
    assert await queue.read() == b"world!"


@pytest.mark.asyncio
async def test_read_waits_for_data() -> None:
    loop = asyncio.get_running_loop()
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        _FakeProtocol(), limit=64, loop=loop
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
    loop = asyncio.get_running_loop()
    queue: FlowControlDataQueue[bytes] = FlowControlDataQueue(
        _FakeProtocol(), limit=64, loop=loop
    )

    queue.set_exception(RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        await queue.read()
