from typing import Optional

import codecs

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
        raise ValueError(f'Cannot interpret {s!r} as boolean.')
    else:
        return bool(s)


def httpize(d: Optional[dict]) -> Optional[dict]:
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
