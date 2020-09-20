from fwk.GamePlugin import Plugin
from fwk.Msg import (
        ClientTxMsg,
        InternalHost,
        InternalRegisterGi,
)
from Chat.ChatRoom import ChatRoom


class ChatLobbyPlugin(Plugin):
    gameIdx = 0
    rooms = {}

    def processHost(self, qmsg):
        if qmsg.jmsg:
            self.txQueue.put_nowait(ClientTxMsg(
                ["Unexpected arguments"], qmsg.initiatorWs,
                initiatorWs=qmsg.initiatorWs)) # TODO error messages
            return True

        self.gameIdx += 1
        newRoom = ChatRoom(
                "chat:{}".format(self.gameIdx),
                "Chat Room #{}".format(self.gameIdx))
        self.rooms[self.gameIdx] = newRoom

        self.txQueue.put_nowait(InternalRegisterGi(newRoom,
            initiatorWs=qmsg.initiatorWs))
        return True

    def processMsg(self, qmsg):
        if super(ChatLobbyPlugin, self).processMsg(qmsg):
            return True

        if isinstance(qmsg, InternalHost):
            return self.processHost(qmsg)

        return False


def plugin():
    return ChatLobbyPlugin("chat", "The Chat Game")
