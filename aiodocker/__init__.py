from importlib.metadata import PackageNotFoundError, version

from .docker import Docker
from .exceptions import (
    DockerContainerError,
    DockerContextError,
    DockerContextInvalidError,
    DockerContextTLSError,
    DockerError,
    DockerStreamError,
)
from .reference import (
    DEFAULT_DOMAIN,
    LEGACY_DEFAULT_DOMAIN,
    OFFICIAL_REPO_PREFIX,
    is_valid_domain,
    split_docker_domain,
    split_image_reference,
)


try:
    __version__ = version("aiodocker")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "0.0.0+unknown"


__all__ = (
    "DEFAULT_DOMAIN",
    "LEGACY_DEFAULT_DOMAIN",
    "OFFICIAL_REPO_PREFIX",
    "Docker",
    "DockerContainerError",
    "DockerContextError",
    "DockerContextInvalidError",
    "DockerContextTLSError",
    "DockerError",
    "DockerStreamError",
    "is_valid_domain",
    "split_docker_domain",
    "split_image_reference",
)
