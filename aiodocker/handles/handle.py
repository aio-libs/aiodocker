import os


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
