class Plugin(object):
    def __init__(self, path, name):
        self.path = path
        self.name = name
        self.rxQueue = None
        self.txQueue = None

    def setRxTxQueues(self, rxQueue, txQueue):
        assert not self.rxQueue
        assert not self.txQueue
        assert rxQueue
        assert txQueue
        self.rxQueue = rxQueue
        self.txQueue = txQueue

    async def worker(self):
        raise NotImplementedError
