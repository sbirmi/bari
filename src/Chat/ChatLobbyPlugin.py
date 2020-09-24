"""Chat lobby plugin. This allows hosting/creating ChatRooms"""
from fwk.GamePlugin import GameLobbyPlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalRegisterGi,
)
from fwk.MsgType import MTYPE_HOST_BAD
from Chat.ChatRoom import ChatRoom


class ChatLobbyPlugin(GameLobbyPlugin):
    """Game lobby for chat rooms"""
    gameIdx = 0
    rooms = {}

    def processHost(self, qmsg):
        if qmsg.jmsg:
            self.txQueue.put_nowait(ClientTxMsg(
                [MTYPE_HOST_BAD, "Unexpected parameters"], {qmsg.initiatorWs},
                initiatorWs=qmsg.initiatorWs))
            return True

        self.gameIdx += 1
        newRoom = ChatRoom("chat:{}".format(self.gameIdx),
                           "Chat Room #{}".format(self.gameIdx))
        self.rooms[self.gameIdx] = newRoom

        self.txQueue.put_nowait(InternalRegisterGi(newRoom,
                                                   initiatorWs=qmsg.initiatorWs))
        return True


def plugin(): # pylint: disable=missing-function-docstring
    return ChatLobbyPlugin("chat", "The Chat Game")
