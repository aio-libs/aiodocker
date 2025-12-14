from importlib.metadata import PackageNotFoundError, version

from .docker import Docker
from .exceptions import (
    DockerAPIError,
    DockerContainerError,
    DockerContextError,
    DockerContextInvalidError,
    DockerContextTLSError,
    DockerError,
)


try:
    __version__ = version("aiodocker")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "0.0.0+unknown"


__all__ = (
    "Docker",
    "DockerAPIError",
    "DockerContainerError",
    "DockerContextError",
    "DockerContextInvalidError",
    "DockerContextTLSError",
    "DockerError",
)
