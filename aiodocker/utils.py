import asyncio
import sys
from typing import Optional, Dict, List, Union, Any, BinaryIO, IO
from io import BytesIO
import tempfile
import tarfile
import codecs
import json
import base64


async def parse_result(response, response_type=None):
    '''
    Convert the response to native objects by the given response type
    or the auto-detected HTTP content-type.
    It also ensures release of the response object.
    '''
    try:
        if not response_type:
            ct = response.headers.get("Content-Type", "")
            if 'json' in ct:
                response_type = 'json'
            elif 'x-tar' in ct:
                response_type = 'tar'
            elif 'text/plain' in ct:
                response_type = 'text'
            else:
                raise TypeError("Unrecognized response type: {ct}"
                                .format(ct=ct))
        if 'tar' == response_type:
            what = await response.read()
            return tarfile.open(mode='r', fileobj=BytesIO(what))
        if 'json' == response_type:
            data = await response.json(encoding='utf-8')
        elif 'text' == response_type:
            data = await response.text(encoding='utf-8')
        else:
            data = await response.read()
        return data
    finally:
        await response.release()


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


def httpize(d: Optional[Dict]) -> Dict[str, Any]:
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


def clean_config(config: Optional[dict]) -> dict:
    """
    Checks the values inside `config`
    Returns a new dictionary with only NOT `None` values
    """
    data = {}
    if isinstance(config, dict):
        for k, v in config.items():
            if v is not None:
                data[k] = v

    return data


def format_env(key, value: Union[None, bytes, str]) -> str:
    """
    Formats envs from {key:value} to ['key=value']
    """
    if value is None:
        return key
    if isinstance(value, bytes):
        value = value.decode('utf-8')

    return "{key}={value}".format(key=key, value=value)


def clean_networks(networks: Optional[List]=None) -> List:
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
