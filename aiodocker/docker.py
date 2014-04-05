import urllib
import aiohttp
import asyncio
import json
import datetime as dt



class Docker:
    def __init__(self, url):
        self.url = url

    def _endpoint(self, path, **kwargs):
        string = "/".join([self.url, path])
        if kwargs:
            string += "?" + urllib.parse.urlencode(kwargs)
        return string

    def _query(self, path, **kwargs):
        url = self._endpoint(path, **kwargs)
        response = yield from aiohttp.request('GET', url)
        chunk = yield from response.content.read()  # XXX: Correct?
        return json.loads(chunk.decode('utf-8'))

    @asyncio.coroutine
    def containers(self, **kwargs):
        data = yield from self._query("containers/json", **kwargs)
        return data

    @asyncio.coroutine
    def container(self, container, **kwargs):
        data = yield from self._query(
            "containers/{}/json".format(container), **kwargs)
        return data

    @asyncio.coroutine
    def events(self, callback):
        response = yield from aiohttp.request('GET', self._endpoint('events'))
        while True:
            try:
                chunk = yield from response.content.read()  # XXX: Correct?
                data = json.loads(chunk.decode('utf-8'))
                if 'time' in data:
                    data['time'] = dt.datetime.fromtimestamp(data['time'])

                if 'id' in data:
                    data['container'] = yield from self.container(data['id'])

                yield from callback(data)
            except aiohttp.EofStream:
                break
        response.close()
