from aiohttp import web


class Handle:
    def __init__(self, docker):
        self._docker = docker

    def url(self, path):
        return ''.join([self.host, path])

    @property
    def docker(self):
        return self._docker

    @property
    def host(self):
        return self.docker.host

    @property
    def client(self):
        return self._docker.client

    @staticmethod
    def _check_status(status):
        if status == 304:
            raise web.HTTPNotModified()
        elif status == 400:
            raise web.HTTPBadRequest()
        elif status == 403:
            raise web.HTTPForbidden()
        elif status == 404:
            raise web.HTTPNotFound()
        elif status == 406:
            raise web.HTTPNotAcceptable()
        elif status == 409:
            raise web.HTTPConflict()
        elif status == 500:
            raise web.HTTPInternalServerError()
