from fwk.GamePlugin import Plugin
from Chat.ChatRoom import ChatRoom

class ChatLobbyPlugin(Plugin):
    gameIdx = 0
    rooms = {}

    async def worker(self):
        print(self.path, "waiting for messages")
        while True:
            rxWs, jmsg = await self.rxQueue.get()
            self.rxQueue.task_done()
            print("Received:", jmsg)

            if jmsg == [self.path, "CONNECT"]:
                # Ignore
                continue

            if jmsg == [self.path, "DISCONNECT"]:
                # Ignore
                continue

            if jmsg != [ self.path, "HOST" ]:
                self.txQueue.put_nowait((rxWs, "bad-command"))
                continue

            self.gameIdx += 1
            newRoom = ChatRoom(
                    "chat:{}".format(self.gameIdx),
                    "Chat Room #{}".format(self.gameIdx))
            self.rooms[self.gameIdx] = newRoom

            self.txQueue.put_nowait(("HOST", newRoom))

def plugin():
    return ChatLobbyPlugin("chat", "The Chat Game")
