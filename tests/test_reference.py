from __future__ import annotations

import base64
import json

import pytest

from aiodocker.reference import (
    DEFAULT_DOMAIN,
    is_valid_domain,
    split_docker_domain,
    split_image_reference,
)
from aiodocker.utils import compose_auth_header


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        # A single element is never a domain, official images gain a prefix
        ("nginx", (DEFAULT_DOMAIN, "library/nginx")),
        ("nginx:latest", (DEFAULT_DOMAIN, "library/nginx:latest")),
        # A namespace is not a domain
        ("library/nginx", (DEFAULT_DOMAIN, "library/nginx")),
        ("aiolibs/aiodocker", (DEFAULT_DOMAIN, "aiolibs/aiodocker")),
        # A dot or colon means a domain
        ("ghcr.io/aio-libs/aiodocker", ("ghcr.io", "aio-libs/aiodocker")),
        ("ghcr.io/aio-libs/aiodocker:1.0", ("ghcr.io", "aio-libs/aiodocker:1.0")),
        ("127.0.0.1/base", ("127.0.0.1", "base")),
        ("myregistry:5000/base", ("myregistry:5000", "base")),
        ("myregistry:5000/team/base:1.0", ("myregistry:5000", "team/base:1.0")),
        # Bracketed IPv6, with and without a port
        ("[::1]/base", ("[::1]", "base")),
        ("[::1]:5000/base", ("[::1]:5000", "base")),
        # localhost is a reserved namespace and always a domain
        ("localhost/base", ("localhost", "base")),
        ("localhost:5000/base", ("localhost:5000", "base")),
        # The legacy Docker Hub domain is canonicalized
        ("index.docker.io/library/nginx", (DEFAULT_DOMAIN, "library/nginx")),
        ("index.docker.io/nginx", (DEFAULT_DOMAIN, "library/nginx")),
        # Uppercase is not allowed in a path component, so it is a domain
        ("Registry/base", ("Registry", "base")),
    ],
)
def test_split_docker_domain(reference: str, expected: tuple[str, str]) -> None:
    assert split_docker_domain(reference) == expected


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("nginx", ("nginx", None, None)),
        ("nginx:latest", ("nginx", "latest", None)),
        ("library/nginx:1.0", ("library/nginx", "1.0", None)),
        ("ghcr.io/aio-libs/aiodocker", ("ghcr.io/aio-libs/aiodocker", None, None)),
        ("ghcr.io/aio-libs/aiodocker:1.0", ("ghcr.io/aio-libs/aiodocker", "1.0", None)),
        # The port of a registry is not a tag
        ("myregistry:5000/base", ("myregistry:5000/base", None, None)),
        ("myregistry:5000/base:1.0", ("myregistry:5000/base", "1.0", None)),
        ("[::1]:5000/base", ("[::1]:5000/base", None, None)),
        # Digests, with and without a tag
        ("nginx@sha256:0000", ("nginx", None, "sha256:0000")),
        ("nginx:1.0@sha256:0000", ("nginx", "1.0", "sha256:0000")),
        (
            "myregistry:5000/base@sha256:0000",
            ("myregistry:5000/base", None, "sha256:0000"),
        ),
    ],
)
def test_split_image_reference(
    reference: str, expected: tuple[str, str | None, str | None]
) -> None:
    assert split_image_reference(reference) == expected


@pytest.mark.parametrize(
    ("domain", "valid"),
    [
        ("ghcr.io", True),
        ("registry.example.com", True),
        ("myregistry:5000", True),
        ("localhost", True),
        ("localhost:5000", True),
        ("127.0.0.1", True),
        ("[::1]", True),
        ("[2001:db8::1]:5000", True),
        (".ghcr.io", False),
        ("ghcr.io.", False),
        ("-ghcr-.io", False),
        ("ghcr.io:", False),
        ("ghcr.io:port", False),
        ("ghcr.io/aio-libs", False),
        ("", False),
    ],
)
def test_is_valid_domain(domain: str, valid: bool) -> None:
    assert is_valid_domain(domain) is valid


def _server_address(header: str) -> str:
    return json.loads(base64.urlsafe_b64decode(header))["serveraddress"]


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        # A Docker Hub reference resolves to the default registry, whether it
        # names a namespace, no namespace at all, or a Docker Hub domain
        ("aiolibs/aiodocker", DEFAULT_DOMAIN),
        ("nginx", DEFAULT_DOMAIN),
        ("docker.io/aiolibs/aiodocker", DEFAULT_DOMAIN),
        ("index.docker.io/aiolibs/aiodocker", DEFAULT_DOMAIN),
        # A real registry is used as is
        ("ghcr.io/aio-libs/aiodocker", "ghcr.io"),
        ("myregistry:5000/base", "myregistry:5000"),
    ],
)
def test_auth_header_server_address(reference: str, expected: str) -> None:
    """The auth header names the registry host, not a repository namespace."""
    registry, _ = split_docker_domain(reference)
    header = compose_auth_header({"username": "u", "password": "p"}, registry)
    assert _server_address(header) == expected
