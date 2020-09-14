from fwk.GamePlugin import Plugin

class ChatRoom(Plugin):
    def __init__(self, path, name):
        super(ChatRoom, self).__init__(path, name)
        self.ws = set()

    async def worker(self):
        print(self.path, "waiting for messages")
        while True:
            rxWs, jmsg = await self.rxQueue.get()
            self.rxQueue.task_done()

            if jmsg == [self.path, "CONNECT"]:
                self.ws.add(rxWs)
                continue

            if jmsg == [self.path, "DISCONNECT"]:
                self.ws.remove(rxWs)
                continue

            print("Received:", jmsg)
            for ws in self.ws:
                self.txQueue.put_nowait((ws, jmsg[1:]))
