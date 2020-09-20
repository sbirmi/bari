from fwk.GamePlugin import Plugin
from fwk.Msg import (
        InternalHost,
        InternalGiStatus,
        MTYPE_GAME_STATUS,
)

LOBBY_PATH = "lobby"

class LobbyPlugin(Plugin):
    giStatusByPath = {}

    def processHost(self, hostMsg):
        # Host, <path>, <details>
        self.txQueue.put_nowait(
                InternalHost(hostMsg.jmsg[2:],
                    hostMsg.jmsg[1],
                    initiatorWs=hostMsg.initiatorWs))
        return True

    def processMsg(self, qmsg):
        if super(LobbyPlugin, self).processMsg(qmsg):
            return True

        if isinstance(qmsg, InternalGiStatus):
            self.giStatusByPath[qmsg.fromPath] = qmsg.jmsg
            self.broadcast([MTYPE_GAME_STATUS, qmsg.fromPath] + qmsg.jmsg)
            return True

        if qmsg.jmsg[0] == "HOST":
            return self.processHost(qmsg)

        return False

def plugin():
    return LobbyPlugin(LOBBY_PATH, "Game Lobby")
