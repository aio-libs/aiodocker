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
