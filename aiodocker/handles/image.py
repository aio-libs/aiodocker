import asyncio
import ujson
from base64 import b64encode

from aiodocker.handles import Handle
from aiodocker.records import Image


class ImageHandles(Handle):
    # noinspection PyShadowingBuiltins
    @asyncio.coroutine
    def list(self, all=False):
        headers = {'Content-Type': 'application/json'}
        params = {'all': 1 if all else 0}
        response = yield from self.client.get(
            url=self.url('/images/json'),
            headers=headers,
            params=params
        )

        details = yield from response.json()  # type: list

        images = []
        for brief in details:
            image = self.get(name=brief.get('Id'))
            if image is not None:
                images.append(image)
        return images

    @asyncio.coroutine
    def build(self):
        raise NotImplemented()

    @asyncio.coroutine
    def create(self, name=None, auth=None):
        """
        name = 'ubuntu:16.04' | 'ubuntu' | 'ubuntu@sha256:820ab56aed...'
        auth = {
            'username': 'somebody',
            'password': 'secret',
            'email': 'somebody@sample.com'
        }
        """
        is_tag = False
        is_digest = len(name.split('@')) > 1
        if not is_digest:
            is_tag = len(name.split(':')) > 1
        if not is_tag and not is_digest:
            name += ':latest'

        headers = {'Content-Type': 'application/json'}
        if auth is not None:
            auth_config = ujson.dumps(auth).encode('utf-8')
            headers['X-Registry-Auth'] = b64encode(auth_config).decode('utf-8')

        params = {'fromImage': name}
        response = yield from self.client.post(
            url=self.url('/images/create'),
            headers=headers,
            params=params
        )

        content = []
        while True:
            line = yield from response.content.readline()
            if not line:
                break
            content.append(ujson.loads(line.decode('utf8')))
        yield from response.release()
        return (yield from self.get(name))

    @asyncio.coroutine
    def inspect(self, name):
        headers = {'Content-Type': 'application/json'}
        response = yield from self.client.get(
            url=self.url('/images/{}/json'.format(name)),
            headers=headers
        )
        attrs = yield from response.json()
        message = attrs.get('message')
        if message and message.startswith('No such image'):
            return None
        return attrs

    @asyncio.coroutine
    def get(self, name):
        attrs = yield from self.inspect(name=name)
        history = yield from self.history(name=name)
        if attrs is None or history is None:
            return None
        return Image(attrs=attrs, history=history, docker=self.docker)

    @asyncio.coroutine
    def history(self, name):
        headers = {'Content-Type': 'application/json'}
        response = yield from self.client.get(
            url=self.url('/images/{}/history'.format(name)),
            headers=headers
        )
        history = yield from response.json()
        if not isinstance(history, list):
            return None
        return history
