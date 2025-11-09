from __future__ import annotations

import enum
from collections.abc import (
    Mapping,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Protocol,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
)

import aiohttp


if TYPE_CHECKING:
    from .containers import DockerContainer


_T_co = TypeVar("_T_co", covariant=True)


class SupportsRead(Protocol[_T_co]):
    def read(self, length: int = ..., /) -> _T_co: ...


# NOTE: Currently these types are used to annotate arguments only.
# When returning values, we need extra type-narrowing for individual fields,
# so it is better to define per-API typed DTOs.
JSONValue: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    Mapping[str, "JSONValue"],
    Sequence["JSONValue"],
]
JSONObject: TypeAlias = Mapping[str, JSONValue]
JSONList: TypeAlias = Sequence[JSONValue]


MutableJSONValue: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    MutableMapping[str, "JSONValue"],
    MutableSequence["JSONValue"],
]
MutableJSONObject: TypeAlias = MutableMapping[str, MutableJSONValue]
MutableJSONList: TypeAlias = MutableSequence[MutableJSONValue]


class AsyncContainerFactory(Protocol):
    async def __call__(self, config: dict[str, Any], name: str) -> DockerContainer: ...


@dataclass(slots=True)
class Timeout:
    connect: Optional[float] = None

    def to_aiohttp_client_timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(
            connect=self.connect,
            total=None,
        )


class PortInfo(TypedDict):
    HostIp: str
    HostPort: str


class Sentinel(enum.Enum):
    TOKEN = enum.auto()


SENTINEL = Sentinel.TOKEN
