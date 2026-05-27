from __future__ import annotations

import aiohttp
import pytest

from aiodocker.docker import Docker


@pytest.fixture
def docker_url(monkeypatch: pytest.MonkeyPatch) -> str:
    """A fake docker host so Docker() can be constructed without a daemon."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")
    return "tcp://127.0.0.1:2375"


async def test_close_default_closes_session(docker_url: str) -> None:
    """When Docker creates the session itself, close() must close it."""
    docker = Docker()
    assert docker._owns_session is True
    assert docker._owns_connector is True

    await docker.close()

    assert docker.session.closed is True


async def test_close_does_not_close_user_session(docker_url: str) -> None:
    """A caller-supplied session must survive Docker.close()."""
    connector = aiohttp.TCPConnector()
    user_session = aiohttp.ClientSession(connector=connector)
    try:
        docker = Docker(session=user_session)
        assert docker._owns_session is False
        # connector was also caller-supplied transitively via the session,
        # but Docker only tracks what it directly received.
        assert docker._owns_connector is True

        await docker.close()

        assert user_session.closed is False
    finally:
        await user_session.close()


async def test_close_does_not_close_user_connector(docker_url: str) -> None:
    """A caller-supplied connector must survive Docker.close()."""
    user_connector = aiohttp.TCPConnector()
    try:
        docker = Docker(connector=user_connector)
        assert docker._owns_session is True
        assert docker._owns_connector is False

        await docker.close()

        assert docker.session.closed is True
        assert user_connector.closed is False
    finally:
        await user_connector.close()


async def test_close_does_not_close_user_session_and_connector(
    docker_url: str,
) -> None:
    """When both session and connector are caller-owned, leave both alone."""
    user_connector = aiohttp.TCPConnector()
    user_session = aiohttp.ClientSession(connector=user_connector)
    try:
        docker = Docker(connector=user_connector, session=user_session)
        assert docker._owns_session is False
        assert docker._owns_connector is False

        await docker.close()

        assert user_session.closed is False
        assert user_connector.closed is False
    finally:
        await user_session.close()


async def test_close_is_idempotent_default(docker_url: str) -> None:
    """Calling close() twice on a default Docker must not raise."""
    docker = Docker()
    await docker.close()
    await docker.close()
    assert docker.session.closed is True


async def test_close_is_idempotent_user_owned(docker_url: str) -> None:
    """Calling close() twice with caller-supplied session must not raise."""
    user_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector())
    try:
        docker = Docker(session=user_session)
        await docker.close()
        await docker.close()
        assert user_session.closed is False
    finally:
        await user_session.close()
