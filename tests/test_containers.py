import asyncio
import ujson
import unittest

from aiodocker.docker import Docker
from aiodocker.utils import aiotest


class TestContainers(unittest.TestCase):
    def setUp(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.maxDiff = None

    def tearDown(self):
        self._loop.close()

    @aiotest
    @asyncio.coroutine
    def test_list(self):
        docker = Docker()
        containers = yield from docker.containers.list(all=True)
        print(ujson.dumps(containers[0].attrs, indent=4))
        print(containers)
        self.assertIsInstance(containers, list)
        docker.close()

    @aiotest
    @asyncio.coroutine
    def test_create(self):
        docker = Docker()
        container = yield from docker.containers.create(
            from_image='ubuntu:16.04',
            cmd='bash'
        )
        self.assertIsNotNone(container)
        docker.close()


    @aiotest
    @asyncio.coroutine
    def test_inspect(self):
        docker = Docker()
        yield from docker.containers.create(from_image='ubuntu:16.04')
        attrs = yield from docker.containers.inspect(name='prickly_lumier')
        self.assertIsInstance(attrs, (type(None), dict))
        docker.close()

    # @aiotest
    # @asyncio.coroutine
    # def test_get(self):
    #     docker = Docker()
    #     yield from docker.images.create(name='ubuntu:16.04')
    #     image = yield from docker.images.get(name='ubuntu:16.04')
    #     self.assertIsNotNone(image)
    #     docker.close()

    # @aiotest
    # @asyncio.coroutine
    # def test_history(self):
    #     docker = Docker()
    #     image = yield from docker.images.create(name='ubuntu:16.04')
    #     self.assertIsNotNone(image)
    #     history1 = yield from docker.images.history(name='ubuntu:16.04')
    #     self.assertListEqual(history1, image.history)
    #     docker.close()
