import asyncio

import pytest


@pytest.mark.asyncio
async def test_events_default_task(docker):
    docker.events.subscribe()
    assert docker.events.task is not None
    await docker.close()
    assert docker.events.task is None
    assert docker.events.json_stream is None


@pytest.mark.asyncio
async def test_events_provided_task(docker):
    task = asyncio.ensure_future(docker.events.run())
    docker.events.subscribe(create_task=False)
    assert docker.events.task is None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await docker.close()
    assert docker.events.json_stream is None


@pytest.mark.asyncio
async def test_events_no_task(docker):
    assert docker.events.task is None
    await docker.close()
    assert docker.events.json_stream is None
