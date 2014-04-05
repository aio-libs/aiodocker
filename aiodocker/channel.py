import asyncio


class ChannelIterator:
    def __init__(self, channel):
        self.channel = channel
        self.queue = asyncio.Queue()
        self.channel.queues.append(self.queue)

    def __del__(self):
        self.channel.queues.remove(self.queue)

    @asyncio.coroutine
    def get(self):
        x = yield from self.queue.get()
        return x


class Channel:
    def __init__(self):
        self.queues = []

    @asyncio.coroutine
    def put(self, obj):
        for el in self.queues:
            yield from el.put(obj)

    def listen(self):
        return ChannelIterator(self)
