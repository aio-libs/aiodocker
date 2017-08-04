import asyncio

import pytest


def test_events_default_task(docker):
    loop = asyncio.get_event_loop()
    docker.events.subscribe()
    assert docker.events.task is not None
    loop.run_until_complete(docker.close())
    assert docker.events.task.done()
    assert docker.events.json_stream is None


def test_events_provided_task(docker):
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(docker.events.run())
    docker.events.subscribe(create_task=False)
    assert docker.events.task is None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        loop.run_until_complete(task)
    loop.run_until_complete(docker.close())
    assert docker.events.json_stream is None


def test_events_no_task(docker):
    loop = asyncio.get_event_loop()
    assert docker.events.task is None
    loop.run_until_complete(docker.close())
    assert docker.events.json_stream is None
