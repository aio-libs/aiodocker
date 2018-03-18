import asyncio
import base64
import codecs
from io import BytesIO
import sys
import shlex
from typing import (
    Any, Iterable, Optional, Union,
    MutableMapping, Mapping, Tuple,
    BinaryIO, IO,
)
import tempfile
import tarfile
import json

from distutils.version import StrictVersion

from .. import errors


BYTE_UNITS = {
    'b': 1,
    'k': 1024,
    'm': 1024 * 1024,
    'g': 1024 * 1024 * 1024
}


def compare_version(v1, v2):
    """Compare docker versions

    >>> v1 = '1.9'
    >>> v2 = '1.10'
    >>> compare_version(v1, v2)
    1
    >>> compare_version(v2, v1)
    -1
    >>> compare_version(v2, v2)
    0
    """
    s1 = StrictVersion(v1)
    s2 = StrictVersion(v2)
    if s1 == s2:
        return 0
    elif s1 > s2:
        return -1
    else:
        return 1


def version_lt(v1, v2):
    return compare_version(v1, v2) > 0


def version_gte(v1, v2):
    return not version_lt(v1, v2)


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
        msg = 'Invalid mime-type component: "{0}"'.format(pieces[0])
        raise ValueError(msg)
    if len(pieces) > 1:
        options = {}
        for opt in pieces[1:]:
            opt = opt.strip()
            if not opt:
                continue
            try:
                k, v = opt.split('=', 1)
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


def clean_networks(networks: Iterable[str]=None) -> Iterable[str]:
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


def clean_filters(filters: Mapping=None) -> str:
    """
    Checks the values inside `filters`
    https://docs.docker.com/engine/api/v1.29/#operation/ServiceList
    Returns a new dictionary in the format `map[string][]string` jsonized
    """

    if filters and isinstance(filters, dict):
        for k, v in filters.items():
            if isinstance(v, bool):
                v = 'true' if v else 'false'
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


def compose_auth_header(auth: Union[MutableMapping, str, bytes],
                        registry_addr: str=None) -> str:
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
        if 'identitytoken' in auth:
            pass
        elif 'auth' in auth:
            return compose_auth_header(auth['auth'], registry_addr)
        else:
            if registry_addr:
                auth['serveraddress'] = registry_addr
        auth_json = json.dumps(auth).encode('utf-8')
        auth = base64.b64encode(auth_json).decode('ascii')
    elif isinstance(auth, (str, bytes)):
        # Parse simple "username:password"-formatted strings
        # and attach the server address specified.
        if isinstance(auth, bytes):
            auth = auth.decode('utf-8')
        s = base64.b64decode(auth)
        username, passwd = s.split(b':', 1)
        config = {
            "username": username.decode('utf-8'),
            "password": passwd.decode('utf-8'),
            "email": None,
            "serveraddress": registry_addr,
        }
        auth_json = json.dumps(config).encode('utf-8')
        auth = base64.b64encode(auth_json).decode('ascii')
    else:
        raise TypeError(
            "auth must be base64 encoded string/bytes or a dictionary")
    return auth


def parse_repository_tag(repo_name):
    parts = repo_name.rsplit('@', 1)
    if len(parts) == 2:
        return tuple(parts)
    parts = repo_name.rsplit(':', 1)
    if len(parts) == 2 and '/' not in parts[1]:
        return tuple(parts)
    return repo_name, None


def parse_bytes(s):
    if isinstance(s, (int, float)):
        return s
    if len(s) == 0:
        return 0

    if s[-2:-1].isalpha() and s[-1].isalpha():
        if s[-1] == "b" or s[-1] == "B":
            s = s[:-1]
    units = BYTE_UNITS
    suffix = s[-1].lower()

    # Check if the variable is a string representation of an int
    # without a units part. Assuming that the units are bytes.
    if suffix.isdigit():
        digits_part = s
        suffix = 'b'
    else:
        digits_part = s[:-1]

    if suffix in units.keys() or suffix.isdigit():
        try:
            digits = int(digits_part)
        except ValueError:
            raise errors.DockerException(
                'Failed converting the string value for memory ({0}) to'
                ' an integer.'.format(digits_part)
            )

        # Reconvert to long for the final result
        s = int(digits * units[suffix])
    else:
        raise errors.DockerException(
            'The specified value for memory ({0}) should specify the'
            ' units. The postfix should be one of the `b` `k` `m` `g`'
            ' characters'.format(s)
        )

    return s


def parse_devices(devices):
    device_list = []
    for device in devices:
        if isinstance(device, dict):
            device_list.append(device)
            continue
        if not isinstance(device, str):
            raise errors.DockerException(
                'Invalid device type {0}'.format(type(device))
            )
        device_mapping = device.split(':')
        if device_mapping:
            path_on_host = device_mapping[0]
            if len(device_mapping) > 1:
                path_in_container = device_mapping[1]
            else:
                path_in_container = path_on_host
            if len(device_mapping) > 2:
                permissions = device_mapping[2]
            else:
                permissions = 'rwm'
            device_list.append({
                'PathOnHost': path_on_host,
                'PathInContainer': path_in_container,
                'CgroupPermissions': permissions
            })
    return device_list


def _convert_port_binding(binding):
    result = {'HostIp': '', 'HostPort': ''}
    if isinstance(binding, tuple):
        if len(binding) == 2:
            result['HostPort'] = binding[1]
            result['HostIp'] = binding[0]
        elif isinstance(binding[0], str):
            result['HostIp'] = binding[0]
        else:
            result['HostPort'] = binding[0]
    elif isinstance(binding, dict):
        if 'HostPort' in binding:
            result['HostPort'] = binding['HostPort']
            if 'HostIp' in binding:
                result['HostIp'] = binding['HostIp']
        else:
            raise ValueError(binding)
    else:
        result['HostPort'] = binding

    if result['HostPort'] is None:
        result['HostPort'] = ''
    else:
        result['HostPort'] = str(result['HostPort'])

    return result


def convert_port_bindings(port_bindings):
    result = {}
    for k, v in port_bindings.items():
        key = str(k)
        if '/' not in key:
            key += '/tcp'
        if isinstance(v, list):
            result[key] = [_convert_port_binding(binding) for binding in v]
        else:
            result[key] = [_convert_port_binding(v)]
    return result


def convert_volume_binds(binds):
    if isinstance(binds, list):
        return binds

    result = []
    for k, v in binds.items():
        if isinstance(k, bytes):
            k = k.decode('utf-8')

        if isinstance(v, dict):
            if 'ro' in v and 'mode' in v:
                raise ValueError(
                    'Binding cannot contain both "ro" and "mode": {}'
                    .format(repr(v))
                )

            bind = v['bind']
            if isinstance(bind, bytes):
                bind = bind.decode('utf-8')

            if 'ro' in v:
                mode = 'ro' if v['ro'] else 'rw'
            elif 'mode' in v:
                mode = v['mode']
            else:
                mode = 'rw'

            result.append('{0}:{1}:{2}').format(k, bind, mode)
        else:
            if isinstance(v, bytes):
                v = v.decode('utf-8')
            result.append('{0}:{1}:rw').format(k, v)
    return result


def convert_tmpfs_mounts(tmpfs):
    if isinstance(tmpfs, dict):
        return tmpfs

    if not isinstance(tmpfs, list):
        raise ValueError(
            'Expected tmpfs value to be either a list or a dict, found: {}'
            .format(type(tmpfs).__name__)
        )

    result = {}
    for mount in tmpfs:
        if isinstance(mount, str):
            if ":" in mount:
                name, options = mount.split(":", 1)
            else:
                name = mount
                options = ""

        else:
            raise ValueError(
                "Expected item in tmpfs list to be a string, found: {}"
                .format(type(mount).__name__)
            )

        result[name] = options
    return result


def normalize_links(links):
    if isinstance(links, dict):
        links = links.items()

    return ['{0}:{1}'.format(k, v) for k, v in sorted(links)]


def split_command(command):
    return shlex.split(command)


def format_environment(environment):
    def format_env(key, value):
        if value is None:
            return key
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        return u'{key}={value}'.format(key=key, value=value)
    return [format_env(*var) for var in environment.items()]


def format_extra_hosts(extra_hosts, task=False):
    # Use format dictated by Swarm API if container is part of a task
    if task:
        return [
            '{} {}'.format(v, k) for k, v in sorted(extra_hosts.items())
        ]

    return [
        '{}:{}'.format(k, v) for k, v in sorted(extra_hosts.items)
    ]
