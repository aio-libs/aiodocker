from __future__ import annotations

from typing import (
    Mapping,
    Protocol,
    Sequence,
    TypeVar,
    Union,
)

from typing_extensions import TypeAlias


_T_co = TypeVar("_T_co", covariant=True)


class SupportsRead(Protocol[_T_co]):
    def read(self, length: int = ..., /) -> _T_co: ...


JSONValue: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    Mapping[str, "JSONValue"],
    Sequence["JSONValue"],
]
JSONObject: TypeAlias = Mapping[str, "JSONValue"]
JSONList: TypeAlias = Sequence["JSONValue"]
