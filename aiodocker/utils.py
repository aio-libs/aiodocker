import asyncio
import base64
import codecs
from io import BytesIO
import sys
from typing import (
    Any, Iterable, List, Optional, Union,
    Mapping, Tuple,
    BinaryIO, IO,
)
import tempfile
import tarfile
import json


async def parse_result(response, response_type=None, *,
                       encoding='utf-8'):
    '''
    Convert the response to native objects by the given response type
    or the auto-detected HTTP content-type.
    It also ensures release of the response object.
    '''
    if response_type is None:
        ct = response.headers.get('content-type')
        if ct is None:
            raise TypeError('Cannot auto-detect respone type '
                            'due to missing Content-Type header.')
        main_type, sub_type, extras = parse_content_type(ct)
        if sub_type == 'json':
            response_type = 'json'
        elif sub_type == 'x-tar':
            response_type = 'tar'
        elif (main_type, sub_type) == ('text', 'plain'):
            response_type = 'text'
            encoding = extras.get('charset', encoding)
        else:
            raise TypeError("Unrecognized response type: {ct}"
                            .format(ct=ct))
    if 'tar' == response_type:
        what = await response.read()
        return tarfile.open(mode='r', fileobj=BytesIO(what))
    if 'json' == response_type:
        data = await response.json(encoding=encoding)
    elif 'text' == response_type:
        data = await response.text(encoding=encoding)
    else:
        data = await response.read()
    return data


def parse_content_type(ct: str) -> Tuple[str, str, Mapping[str, str]]:
    '''
    Decompose the value of HTTP "Content-Type" header into
    the main/sub MIME types and other extra options as a dictionary.
    All parsed values are lower-cased automatically.
    '''
    pieces = ct.split(';')
    try:
        main_type, sub_type = pieces[0].split('/')
    except ValueError:
        raise ValueError('Invalid mime-type component: "{0}"'.format(pieces[0]))
    if len(pieces) > 1:
        options = {}
        for opt in pieces[1:]:
            opt = opt.strip()
            if not opt:
                continue
            try:
                k, v = opt.split('=', 1)
            except ValueError:
                raise ValueError('Invalid option component: "{0}"'.format(opt))
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


_true_strs = frozenset(['true', 'yes', 'y', '1'])
_false_strs = frozenset(['false', 'no', 'n', '0'])


def human_bool(s) -> bool:
    if isinstance(s, str):
        if s.lower() in _true_strs:
            return True
        if s.lower() in _false_strs:
            return False
        raise ValueError('Cannot interpret {s!r} as boolean.'.format(s=s))
    else:
        return bool(s)


def httpize(d: Optional[Mapping]) -> Mapping[str, Any]:
    if d is None:
        return None
    converted = {}
    for k, v in d.items():
        if isinstance(v, bool):
            v = '1' if v else '0'
        if not isinstance(v, str):
            v = str(v)
        converted[k] = v
    return converted


class _DecodeHelper:
    """
    Decode logs from the Docker Engine
    """

    def __init__(self, generator, encoding):
        self._gen = generator.__aiter__()
        self._decoder = codecs.getincrementaldecoder(encoding)(errors='ignore')
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
            stream_decoded = self._decoder.decode(b'', final=True)
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
        value = value.decode('utf-8')

    return "{key}={value}".format(key=key, value=value)


def clean_networks(networks: Optional[Iterable[str]]=None) -> Iterable[str]:
    """
    Cleans the values inside `networks`
    Returns a new list
    """
    if not networks:
        return networks
    if not isinstance(networks, list):
        raise TypeError('networks parameter must be a list.')

    result = []
    for n in networks:
        if isinstance(n, str):
            n = {'Target': n}
        result.append(n)
    return result


def clean_filters(filters: Optional[dict]=None) -> str:
    """
    Checks the values inside `filters`
    https://docs.docker.com/engine/api/v1.29/#operation/ServiceList
    Returns a new dictionary in the format `map[string][]string` jsonized
    """

    if filters and isinstance(filters, dict):
        for k, v in filters.items():
            if not isinstance(v, list):
                v = [v, ]
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
    t = tarfile.open(mode='w:gz', fileobj=f)

    if isinstance(fileobject, BytesIO):
        dfinfo = tarfile.TarInfo('Dockerfile')
        dfinfo.size = len(fileobject.getvalue())
        fileobject.seek(0)
    else:
        dfinfo = t.gettarinfo(fileobj=fileobject, arcname='Dockerfile')

    t.addfile(dfinfo, fileobject)
    t.close()
    f.seek(0)
    return f


def parse_base64_auth(auth: str, repo: str) -> str:
    """
    parse base64 user password
    :param auth: base64 auth string
    :param repo: repo server
    :return: base64 X-Registry-Auth header
    """
    s = base64.b64decode(auth)
    username, pwd = s.split(b':', 1)
    u = username.decode('utf-8')
    p = pwd.decode('utf-8')

    auth_config = {"username": u, "password": p,
                   "email": None, "serveraddress": repo}

    auth_config_json = json.dumps(auth_config).encode('ascii')
    auth_config_b64 = base64.urlsafe_b64encode(auth_config_json)
    return auth_config_b64.decode('ascii')
