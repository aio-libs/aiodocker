class Record:
    def __init__(self, attrs=None, docker=None):
        self._docker = docker
        self._attrs = {} if attrs is None else attrs

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.short_id)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.id == other.id

    @property
    def docker(self):
        return self._docker

    @property
    def attrs(self):
        return self._attrs

    @property
    def id(self):
        return self._attrs.get('Id')

    @property
    def short_id(self):
        return self.id[:10]
