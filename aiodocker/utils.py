from typing import Optional, Dict, Any, BinaryIO, IO
from io import BytesIO
import tempfile
import tarfile
import codecs
import json



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


async def decoded(generator, encoding='utf-8'):
    decoder = codecs.getincrementaldecoder(encoding)(errors='ignore')
    async for d in generator:
        yield decoder.decode(d)

    d = decoder.decode(b'', final=True)
    if d:
        yield d


def clean_config(config: Optional[dict]) -> dict:
    """
    Check the values inside `config`
    Return a new dictionary with only NOT `None` values
    """

    data = {}
    if isinstance(config, dict):
        for k, v in config.items():
            if v is not None:
                data[k] = v

    return data


def format_env(key, value):
    """
    Format envs from {key:value} to ['key=value']
    """
    if value is None:
        return key
    if isinstance(value, bytes):
        value = value.decode('utf-8')

    return f"{key}={value}"


def clean_networks(networks: Optional[list]=None) -> list:
    """
    Clean the values inside `networks`
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
    Check the values inside `filters`
    https://docs.docker.com/engine/api/v1.29/#operation/ServiceList
    Returns a new dictionary in the format `map[string][]string` jsonized
    """

    if filters:
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