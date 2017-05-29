import json
import pytest
from aiodocker import utils


def test_clean_config():
    dirty_dict = {
        "a": None,
        "b": {},
        "c": [],
        "d": 1,
    }
    clean_dict = {
        "b": {},
        "c": [],
        "d": 1,
    }
    clean_config = utils.clean_config(dirty_dict)
    assert clean_config == clean_dict


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
