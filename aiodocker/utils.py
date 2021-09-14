import asyncio
import base64
import codecs
import json
import sys
import tarfile
import tempfile
from io import BytesIO
from typing import (
    IO,
    Any,
    BinaryIO,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union,
)


async def parse_result(response, response_type=None, *, encoding="utf-8"):
    """
    Convert the response to native objects by the given response type
    or the auto-detected HTTP content-type.
    It also ensures release of the response object.
    """
    if response_type is None:
        ct = response.headers.get("content-type")
        if ct is None:
            cl = response.headers.get("content-length")
            if cl is None or cl == "0":
                return ""
            raise TypeError(
                "Cannot auto-detect response type "
                "due to missing Content-Type header."
            )
        main_type, sub_type, extras = parse_content_type(ct)
        if sub_type == "json":
            response_type = "json"
        elif sub_type == "x-tar":
            response_type = "tar"
        elif (main_type, sub_type) == ("text", "plain"):
            response_type = "text"
            encoding = extras.get("charset", encoding)
        else:
            raise TypeError("Unrecognized response type: {ct}".format(ct=ct))
    if "tar" == response_type:
        what = await response.read()
        return tarfile.open(mode="r", fileobj=BytesIO(what))
    if "json" == response_type:
        data = await response.json(encoding=encoding)
    elif "text" == response_type:
        data = await response.text(encoding=encoding)
    else:
        data = await response.read()
    return data


def parse_content_type(ct: str) -> Tuple[str, str, Mapping[str, str]]:
    """
    Decompose the value of HTTP "Content-Type" header into
    the main/sub MIME types and other extra options as a dictionary.
    All parsed values are lower-cased automatically.
    """
    pieces = ct.split(";")
    try:
        main_type, sub_type = pieces[0].split("/")
    except ValueError:
        msg = 'Invalid mime-type component: "{0}"'.format(pieces[0])
        raise ValueError(msg)
    if len(pieces) > 1:
        options = {}
        for opt in pieces[1:]:
            opt = opt.strip()
            if not opt:
                continue
            try:
                k, v = opt.split("=", 1)
            except ValueError:
                msg = 'Invalid option component: "{0}"'.format(opt)
                raise ValueError(msg)
            else:
                options[k.lower()] = v.lower()
    else:
        options = {}
    return main_type.lower(), sub_type.lower(), options


def identical(d1, d2):
    if type(d1) != type(d2):
        return False

    if isinstance(d1, dict):
        keys = set(d1.keys()) | set(d2.keys())
        for key in keys:
            if not identical(d1.get(key, {}), d2.get(key, {})):
                return False
        return True

    if isinstance(d1, list):
        if len(d1) != len(d2):
            return False

        pairs = zip(d1, d2)
        return all((identical(x, y) for (x, y) in pairs))

    return d1 == d2


_true_strs = frozenset(["true", "yes", "y", "1"])
_false_strs = frozenset(["false", "no", "n", "0"])


def human_bool(s) -> bool:
    if isinstance(s, str):
        if s.lower() in _true_strs:
            return True
        if s.lower() in _false_strs:
            return False
        raise ValueError("Cannot interpret {s!r} as boolean.".format(s=s))
    else:
        return bool(s)


def httpize(d: Optional[Mapping]) -> Optional[Mapping[str, Any]]:
    if d is None:
        return None
    converted = {}
    for k, v in d.items():
        if isinstance(v, bool):
            v = "1" if v else "0"
        if not isinstance(v, str):
            v = json.dumps(v)
        converted[k] = v
    return converted


class _DecodeHelper:
    """
    Decode logs from the Docker Engine
    """

    def __init__(self, generator, encoding):
        self._gen = generator.__aiter__()
        self._decoder = codecs.getincrementaldecoder(encoding)(errors="ignore")
        self._flag = False

    def __aiter__(self):
        return self

    # to make it compatible with Python 3.5.0 and 3.5.2
    # https://www.python.org/dev/peps/pep-0492/#api-design-and-implementation-revisions
    if sys.version_info <= (3, 5, 2):
        __aiter__ = asyncio.coroutine(__aiter__)

    async def __anext__(self):
        if self._flag:
            raise StopAsyncIteration

        # we catch StopAsyncIteration from self._gen
        # because we need to close the decoder
        # then we raise StopAsyncIteration checking self._flag
        try:
            stream = await self._gen.__anext__()
        except StopAsyncIteration:
            self._flag = True
            stream_decoded = self._decoder.decode(b"", final=True)
            if stream_decoded:
                return stream_decoded
            raise StopAsyncIteration
        else:
            return self._decoder.decode(stream)


def clean_map(obj: Mapping[Any, Any]) -> Mapping[Any, Any]:
    """
    Return a new copied dictionary without the keys with ``None`` values from
    the given Mapping object.
    """
    return {k: v for k, v in obj.items() if v is not None}


def format_env(key, value: Union[None, bytes, str]) -> str:
    """
    Formats envs from {key:value} to ['key=value']
    """
    if value is None:
        return key
    if isinstance(value, bytes):
        value = value.decode("utf-8")

    return "{key}={value}".format(key=key, value=value)


def clean_networks(networks: Iterable[str] = None) -> Optional[Iterable[str]]:
    """
    Cleans the values inside `networks`
    Returns a new list
    """
    if not networks:
        return networks
    if not isinstance(networks, list):
        raise TypeError("networks parameter must be a list.")

    result = []
    for n in networks:
        if isinstance(n, str):
            n = {"Target": n}
        result.append(n)
    return result


def clean_filters(filters: Mapping = None) -> str:
    """
    Checks the values inside `filters`
    https://docs.docker.com/engine/api/v1.29/#operation/ServiceList
    Returns a new dictionary in the format `map[string][]string` jsonized
    """

    if filters and isinstance(filters, dict):
        for k, v in filters.items():
            if not isinstance(v, list):
                v = [v]
            filters[k] = v

    return json.dumps(filters)


def mktar_from_dockerfile(fileobject: BinaryIO) -> IO:
    """
    Create a zipped tar archive from a Dockerfile
    **Remember to close the file object**
    Args:
        fileobj: a Dockerfile
    Returns:
        a NamedTemporaryFile() object
    """

    f = tempfile.NamedTemporaryFile()
    t = tarfile.open(mode="w:gz", fileobj=f)

    if isinstance(fileobject, BytesIO):
        dfinfo = tarfile.TarInfo("Dockerfile")
        dfinfo.size = len(fileobject.getvalue())
        fileobject.seek(0)
    else:
        dfinfo = t.gettarinfo(fileobj=fileobject, arcname="Dockerfile")

    t.addfile(dfinfo, fileobject)
    t.close()
    f.seek(0)
    return f


def compose_auth_header(
    auth: Union[MutableMapping, str, bytes], registry_addr: str = None
) -> str:
    """
    Validate and compose base64-encoded authentication header
    with an optional support for parsing legacy-style "user:password"
    strings.

    Args:
        auth: Authentication information
        registry_addr: An address of the registry server

    Returns:
        A base64-encoded X-Registry-Auth header value
    """
    if isinstance(auth, Mapping):
        # Validate the JSON format only.
        if "identitytoken" in auth:
            pass
        elif "auth" in auth:
            return compose_auth_header(auth["auth"], registry_addr)
        else:
            if registry_addr:
                auth["serveraddress"] = registry_addr
        auth_json = json.dumps(auth).encode("utf-8")
    elif isinstance(auth, (str, bytes)):
        # Parse simple "username:password"-formatted strings
        # and attach the server address specified.
        if isinstance(auth, bytes):
            auth = auth.decode("utf-8")
        s = base64.b64decode(auth)
        username, passwd = s.split(b":", 1)
        config = {
            "username": username.decode("utf-8"),
            "password": passwd.decode("utf-8"),
            "email": None,
            "serveraddress": registry_addr,
        }
        auth_json = json.dumps(config).encode("utf-8")
    else:
        raise TypeError("auth must be base64 encoded string/bytes or a dictionary")
    auth = base64.b64encode(auth_json).decode("ascii")
    return auth


class _AsyncCM:
    __slots__ = ("_coro", "_resp")

    def __init__(self, coro):
        self._coro = coro
        self._resp = None

    async def __aenter__(self):
        resp = await self._coro
        self._resp = resp
        return await resp.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._resp.__aexit__(exc_type, exc_val, exc_tb)
