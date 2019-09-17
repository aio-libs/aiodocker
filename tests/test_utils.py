import json

import pytest

from aiodocker import utils


def test_clean_mapping():
    dirty_dict = {"a": None, "b": {}, "c": [], "d": 1}
    clean_dict = {"b": {}, "c": [], "d": 1}
    result = utils.clean_map(dirty_dict)
    assert result == clean_dict


def test_parse_content_type():
    ct = "text/plain"
    mt, st, opts = utils.parse_content_type(ct)
    assert mt == "text"
    assert st == "plain"
    assert opts == {}

    ct = "text/plain; charset=utf-8"
    mt, st, opts = utils.parse_content_type(ct)
    assert mt == "text"
    assert st == "plain"
    assert opts == {"charset": "utf-8"}

    ct = "text/plain; "
    mt, st, opts = utils.parse_content_type(ct)
    assert mt == "text"
    assert st == "plain"
    assert opts == {}

    ct = "text/plain; asdfasdf"
    with pytest.raises(ValueError):
        mt, st, opts = utils.parse_content_type(ct)


def test_format_env():
    key = "name"
    value = "hello"
    assert utils.format_env(key, value) == "name=hello"

    key = "name"
    value = None
    assert utils.format_env(key, value) == "name"

    key = "name"
    value = b"hello"
    assert utils.format_env(key, value) == "name=hello"


def test_clean_networks():
    networks = []
    assert utils.clean_networks(networks) == []

    networks = ("test-network-1", "test-network-2")
    with pytest.raises(TypeError) as excinfo:
        result = utils.clean_networks(networks)
    assert "networks parameter must be a list." in str(excinfo.value)

    networks = ["test-network-1", "test-network-2"]
    result = [{"Target": "test-network-1"}, {"Target": "test-network-2"}]
    assert utils.clean_networks(networks) == result


def test_clean_filters():
    filters = {"a": ["1", "2", "3", "4"], "b": "string"}
    result = {"a": ["1", "2", "3", "4"], "b": ["string"]}
    assert utils.clean_filters(filters=filters) == json.dumps(result)

    filters = ()
    result = {"a": ["1", "2", "3", "4"], "b": ["string"]}
    utils.clean_filters(filters=filters) == json.dumps(result)
