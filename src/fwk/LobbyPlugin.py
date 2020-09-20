from collections import OrderedDict

from fwk.GamePlugin import Plugin
from fwk.Msg import (
        ClientTxMsg,
        InternalHost,
        InternalGiStatus,
)
from fwk.MsgType import (
        MTYPE_GAME_STATUS,
        MTYPE_HOST,
)

LOBBY_PATH = "lobby"

class LobbyPlugin(Plugin):
    giStatusByPath = OrderedDict()

    def sendGameStatusToOne(self, path, toWs):
        """Sends game status to one or more client ws"""
        jmsg = [MTYPE_GAME_STATUS, path] + self.giStatusByPath[path]
        self.txQueue.put_nowait(ClientTxMsg(jmsg, toWs))

    def sendGameStatusToAll(self, path):
        self.broadcast([MTYPE_GAME_STATUS, path] + self.giStatusByPath[path])

    def updateGameStatus(self, path, jmsg):
        if path not in self.giStatusByPath or self.giStatusByPath[path] != jmsg:
            self.giStatusByPath[path] = jmsg
            self.giStatusByPath.move_to_end(path)
            self.sendGameStatusToAll(path)

    def postProcessConnect(self, ws):
        # Notify of all ongoing game instances
        for path in self.giStatusByPath:
            self.sendGameStatusToOne(path, ws)

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
            self.updateGameStatus(qmsg.fromPath, qmsg.jmsg)
            return True

        if qmsg.jmsg[0] == MTYPE_HOST:
            return self.processHost(qmsg)

        return False

def plugin():
    return LobbyPlugin(LOBBY_PATH, "Game Lobby")
