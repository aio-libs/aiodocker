import asyncio

from aiodocker.records.record import Record


class Container(Record):
    def __repr__(self):
        return "<%s: '%s'>" % (self.__class__.__name__, self.name)

    @property
    def name(self):
        return self._attrs.get('Name')[1:]

    @property
    def status(self):
        return self._attrs.get('State').get('Status')

    @asyncio.coroutine
    def reload(self):
        self._attrs = yield from self.docker.containers.inspect(
            id_name=self.id
        )
        return self

    @asyncio.coroutine
    def start(self, detach_keys=None):
        yield from self.docker.containers.start(
            id_name=self.id,
            detach_keys=detach_keys
        )

    @asyncio.coroutine
    def stop(self, timeout=None):
        yield from self.docker.containers.stop(
            id_name=self.id,
            timeout=timeout
        )

    @asyncio.coroutine
    def restart(self, timeout=None):
        yield from self.docker.containers.restart(
            id_name=self.id,
            timeout=timeout
        )

    @asyncio.coroutine
    def kill(self, signal=None):
        yield from self.docker.containers.kill(
            id_name=self.id,
            signal=signal
        )

    @asyncio.coroutine
    def rename(self, name=None):
        yield from self.docker.containers.rename(
            id_name=self.id,
            name=name
        )

    @asyncio.coroutine
    def pause(self):
        yield from self.docker.containers.pause(id_name=self.id)

    @asyncio.coroutine
    def unpause(self):
        yield from self.docker.containers.unpause(id_name=self.id)

    @asyncio.coroutine
    def wait(self):
        yield from self.docker.containers.wait(id_name=self.id)

    @asyncio.coroutine
    def remove(self, volumes=None, force=None):
        yield from self.docker.containers.remove(
            id_name=self.id,
            volumes=volumes,
            force=force
        )

