"""Parsing of Docker image references.

Ports the parts of Docker's reference implementation that a client needs to
reason about an image reference, most importantly to tell a registry domain
apart from a repository namespace.

See https://github.com/distribution/reference
"""

from __future__ import annotations

import re


#: Registry domain used when a reference does not name one.
DEFAULT_DOMAIN = "docker.io"
#: Legacy Docker Hub domain, canonicalized to :data:`DEFAULT_DOMAIN`.
LEGACY_DEFAULT_DOMAIN = "index.docker.io"
#: Repository prefix of official Docker Hub images.
OFFICIAL_REPO_PREFIX = "library/"
#: Reserved namespace which is always treated as a domain.
LOCALHOST_DOMAIN = "localhost"

# Port of DomainRegexp, covering domain names, IPv6 addresses and an optional
# port. See https://github.com/distribution/reference/blob/main/regexp.go
_DOMAIN_NAME_COMPONENT = r"(?:[a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])"
_IPV6_ADDRESS = r"\[(?:[a-fA-F0-9:]+)\]"
DOMAIN_REGEX = re.compile(
    rf"(?:{_DOMAIN_NAME_COMPONENT}(?:\.{_DOMAIN_NAME_COMPONENT})*|{_IPV6_ADDRESS})"
    r"(?::[0-9]+)?"
)


def split_docker_domain(reference: str) -> tuple[str, str]:
    """Split an image reference into its registry domain and the remainder.

    The part before the first slash is only a domain when it looks like one, so
    ``"homeassistant/base"`` is a Docker Hub namespace while
    ``"myregistry:5000/base"`` is a registry with a port. A reference without a
    domain resolves to :data:`DEFAULT_DOMAIN`, and an official Docker Hub image
    gains the :data:`OFFICIAL_REPO_PREFIX` prefix, matching ``docker pull``.

    Port of ``splitDockerDomain()``, see
    https://github.com/distribution/reference/blob/main/normalize.go

    >>> split_docker_domain("nginx")
    ('docker.io', 'library/nginx')
    >>> split_docker_domain("homeassistant/base")
    ('docker.io', 'homeassistant/base')
    >>> split_docker_domain("ghcr.io/aio-libs/aiodocker:1.0")
    ('ghcr.io', 'aio-libs/aiodocker:1.0')
    >>> split_docker_domain("myregistry:5000/base")
    ('myregistry:5000', 'base')
    """
    maybe_domain, separator, maybe_remainder = reference.partition("/")
    if not separator:
        # A single element is never a domain
        return DEFAULT_DOMAIN, OFFICIAL_REPO_PREFIX + reference

    if maybe_domain == LOCALHOST_DOMAIN:
        # localhost is a reserved namespace and always considered a domain
        domain, remainder = maybe_domain, maybe_remainder
    elif maybe_domain == LEGACY_DEFAULT_DOMAIN:
        # Canonicalize the legacy Docker Hub domain
        domain, remainder = DEFAULT_DOMAIN, maybe_remainder
    elif "." in maybe_domain or ":" in maybe_domain:
        # A dot or colon means a domain, covering ports, IPv4 and IPv6 as well
        domain, remainder = maybe_domain, maybe_remainder
    elif maybe_domain.lower() != maybe_domain:
        # Uppercase is not allowed in a path component, so it must be a domain
        domain, remainder = maybe_domain, maybe_remainder
    else:
        domain, remainder = DEFAULT_DOMAIN, reference

    if domain == DEFAULT_DOMAIN and "/" not in remainder:
        remainder = OFFICIAL_REPO_PREFIX + remainder

    return domain, remainder


def split_image_reference(reference: str) -> tuple[str, str | None, str | None]:
    """Split an image reference into its name, tag and digest.

    A colon only starts a tag when no slash follows it, so the port of a
    registry stays part of the name. Both the tag and the digest are ``None``
    when the reference does not carry them.

    >>> split_image_reference("nginx:latest")
    ('nginx', 'latest', None)
    >>> split_image_reference("myregistry:5000/base")
    ('myregistry:5000/base', None, None)
    >>> split_image_reference("nginx@sha256:0000")
    ('nginx', None, 'sha256:0000')
    """
    name, separator, digest = reference.partition("@")
    remainder, colon, tag = name.rpartition(":")
    if colon and "/" not in tag:
        name = remainder
    else:
        tag = ""
    return name, tag or None, digest if separator else None


def is_valid_domain(domain: str) -> bool:
    """Return whether the given string matches Docker's registry domain grammar.

    Accepts a domain name, an IPv4 or bracketed IPv6 address, and an optional
    port, rejecting malformed values such as ``".ghcr.io"``. Being a port of
    ``DomainRegexp`` this is a grammar check, so it does not verify that an
    IPv6 literal is semantically valid or that a port is within range, both of
    which Docker leaves to the daemon as well.
    """
    return DOMAIN_REGEX.fullmatch(domain) is not None
