import asyncio
import unittest

from aiodocker.docker import Docker
from aiodocker.utils import aiotest


class TestImages(unittest.TestCase):
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
        images = yield from docker.images.list(all=True)
        self.assertIsInstance(images, list)
        docker.close()

    # @aiotest
    # @asyncio.coroutine
    # def test_build(self):
    #     docker = Docker()
    #     images = yield from docker.images.list(all=True)
    #     print(images)
    #     # yield from docker.images.inspect('ubuntu:16.04')
    #
    #     # yield from docker.images.create(name='ubuntu:14.04')
    #
    #     docker.close()

    @aiotest
    @asyncio.coroutine
    def test_create(self):
        docker = Docker()
        image = yield from docker.images.create(from_image='ubuntu:16.04')
        self.assertIsNotNone(image)
        docker.close()

    @aiotest
    @asyncio.coroutine
    def test_inspect(self):
        docker = Docker()
        attrs = yield from docker.images.inspect(name='ubuntu:16.04')
        self.assertIsInstance(attrs, dict)
        docker.close()

    @aiotest
    @asyncio.coroutine
    def test_history(self):
        docker = Docker()
        image = yield from docker.images.create(from_image='ubuntu:16.04')
        history = yield from docker.images.history(name='ubuntu:16.04')
        self.assertListEqual(history, image.history)
        docker.close()

    @aiotest
    @asyncio.coroutine
    def test_get(self):
        docker = Docker()
        image1 = yield from docker.images.create(from_image='ubuntu:16.04')
        image2 = yield from docker.images.get(name='ubuntu:16.04')
        self.assertEqual(image1.id, image2.id)
        docker.close()

