from fwk.GamePlugin import Plugin
from fwk.Msg import InternalRegisterGi
from Chat.ChatRoom import ChatRoom

class ChatLobbyPlugin(Plugin):
    gameIdx = 0
    rooms = {}

    def processHost(self, qmsg):
        self.gameIdx += 1
        newRoom = ChatRoom(
                "chat:{}".format(self.gameIdx),
                "Chat Room #{}".format(self.gameIdx))
        self.rooms[self.gameIdx] = newRoom

        self.txQueue.put_nowait(InternalRegisterGi(newRoom))
        return True

    def processMsg(self, qmsg):
        if super(ChatLobbyPlugin, self).processMsg(qmsg):
            return True

        if qmsg.jmsg == [self.path, "HOST"]:
            return self.processHost(qmsg)

        return False


def plugin():
    return ChatLobbyPlugin("chat", "The Chat Game")
