import asyncio

from aiodocker.records.record import Record


class Image(Record):
    def __init__(self, attrs=None, history=None, docker=None):
        super().__init__(attrs=attrs, docker=docker)
        self._history = [] if history is None else history

    def __repr__(self):
        return "<%s: '%s'>" % (self.__class__.__name__, "', '".join(self.tags))

    @property
    def short_id(self):
        if self.id.startswith('sha256:'):
            return self.id[:17]
        return self.id[:10]

    @property
    def tags(self):
        tags = self._attrs.get('RepoTags', [])
        return [tag for tag in tags if tag != '<none>:<none>']

    @property
    def history(self):
        return self._history

    @asyncio.coroutine
    def reload(self):
        self._attrs = self.docker.images.inspect(name=self.id)
        self._history = self.docker.images.history(name=self.id)
