"""Tests for ``aiodocker.stream.Stream`` lifecycle warnings."""

import gc
import warnings

import pytest

from aiodocker.stream import Stream


def _make_stream() -> Stream:
    """Construct a ``Stream`` without touching the network."""
    stream = Stream.__new__(Stream)
    stream._setup = None  # type: ignore[assignment]
    stream.docker = None  # type: ignore[assignment]
    stream._resp = None
    stream._closed = False
    stream._timeout = None
    stream._queue = None
    return stream


def test_del_warns_when_resp_set_and_not_closed() -> None:
    stream = _make_stream()
    stream._resp = object()  # type: ignore[assignment]
    stream._closed = False
    with pytest.warns(ResourceWarning, match="Unclosed ExecStream"):
        del stream
        gc.collect()


def test_del_silent_when_resp_is_none() -> None:
    stream = _make_stream()
    assert stream._resp is None
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        del stream
        gc.collect()


def test_del_silent_when_closed() -> None:
    stream = _make_stream()
    stream._resp = object()  # type: ignore[assignment]
    stream._closed = True
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        del stream
        gc.collect()
