import asyncio
import ujson
from base64 import b64encode

from .handle import Handle
from ..records import Image


class ImageHandles(Handle):
    # noinspection PyShadowingBuiltins
    @asyncio.coroutine
    def list(self, all=None, filters=None, filter=None):
        params = {}
        if all is not None:
            params['all'] = int(all)
        if filters is not None:
            params['filters'] = ujson.dumps(filters)
        if filter is not None:
            params['filter'] = filter

        response = yield from self.client.get(
            url=self.url('/images/json'),
            params=params
        )
        self._check_status(response.status)
        details = yield from response.json(encoding='utf-8')  # type: list
        images = []
        for brief in details:
            image = yield from self.get(name=brief.get('Id'))
            if image is not None:
                images.append(image)
        return images

    @asyncio.coroutine
    def build(self):
        raise NotImplemented()

    @asyncio.coroutine
    def create(self, from_image=None, from_src=None, repo=None, tag=None,
               auth=None, callback=None):
        headers = {}
        if auth is not None:
            auth_config = ujson.dumps(auth).encode('utf-8')
            headers['X-Registry-Auth'] = b64encode(auth_config).decode('utf-8')

        params = {}
        if from_image is not None:
            params['fromImage'] = from_image
        if from_src is not None:
            params['fromSrc'] = from_src
        if repo is not None:
            params['repo'] = repo
        if tag is not None:
            params['tag'] = tag

        response = yield from self.client.post(
            url=self.url('/images/create'),
            headers=headers,
            params=params
        )
        self._check_status(response.status)
        while True:
            line = yield from response.content.readline()
            if not line:
                break
            callback(ujson.loads(line.decode('utf8')))
        yield from response.release()
        return (yield from self.get(from_image))

    @asyncio.coroutine
    def inspect(self, name):
        response = yield from self.client.get(
            url=self.url('/images/{}/json'.format(name))
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def history(self, name):
        response = yield from self.client.get(
            url=self.url('/images/{}/history'.format(name))
        )
        self._check_status(response.status)
        return (yield from response.json(encoding='utf-8'))

    @asyncio.coroutine
    def get(self, name):
        attrs = yield from self.inspect(name=name)
        history = yield from self.history(name=name)
        return Image(attrs=attrs, history=history, docker=self.docker)

    @asyncio.coroutine
    def push(self, name, tag=None, auth=None):
        headers = {}
        if auth is not None:
            auth_config = ujson.dumps(auth).encode('utf-8')
            headers['X-Registry-Auth'] = b64encode(auth_config).decode('utf-8')

        params = {}
        if tag is not None:
            params['tag'] = tag

        response = yield from self.client.post(
            url=self.url('/images/{}/push'.format(name)),
            headers=headers,
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def tag(self, name, repo=None, tag=None):
        params = {}
        if tag is not None:
            params['tag'] = tag
        if repo is not None:
            params['repo'] = repo

        response = yield from self.client.get(
            url=self.url('/images/{}/tag'.format(name))
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def delete(self, name, force=None, noprune=None):
        params = {}
        if force is not None:
            params['force'] = force
        if noprune is not None:
            params['noprune'] = noprune

        response = yield from self.client.delete(
            url=self.url('/images/{}'.format(name)),
            params=params
        )
        self._check_status(response.status)

    @asyncio.coroutine
    def search(self, term=None, limit=None, filters=None):
        params = {}
        if term is not None:
            params['term'] = term
        if limit is not None:
            params['limit'] = limit
        if filters is not None:
            params['filters'] = ujson.dumps(filters)

        response = yield from self.client.delete(
            url=self.url('/images/search'),
            params=params
        )
        self._check_status(response.status)
