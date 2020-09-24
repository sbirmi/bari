"""Main lobby (required plugin) in bari.

The plugin here is responsible for:
1. Receiving and relaying MTYPE_HOST messages as an InternalHost
   to the correct game lobby
2. Tracking GAME-STATUS for each game instance
3. Broadcasts/relays GAME-STATUS for each game instance to lobby connections
"""

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
    """The lobby plugin

    Handles:
    1. [ MTYPE_HOST, "<path to game lobby>", (optional) details ]
        a. Emit InternalHost(jmsg=details, path="<path to game lobby>", ...)
    2. InternalGiStatus
        a. Maintains an internal cache giStatusByPath
        b. Any change in giStatusByPath is broadcast to all websockets
    3. InternalConnectWsToGi
        a. Flush all MTYPE_GAME_STATUS to the new connection

    Emits:
    1. InternalHost
    2. [ MTYPE_GAME_STATUS, "<path to game instance>", (optional) details ]
    """
    def __init__(self, path, name):
        super(LobbyPlugin, self).__init__(path, name)
        self.giStatusByPath = OrderedDict()

    def sendGameStatusToOne(self, path, toWs):
        """Sends game instance status to one connection"""
        jmsg = [MTYPE_GAME_STATUS, path] + self.giStatusByPath[path]
        self.txQueue.put_nowait(ClientTxMsg(jmsg, {toWs}))

    def sendGameStatusToAll(self, path):
        """Broadcast 'path' game instance to all connections"""
        self.broadcast([MTYPE_GAME_STATUS, path] + self.giStatusByPath[path])

    def updateGameStatus(self, path, jmsg):
        """Handle InternalGiStatus. Changes are broadcast to all connections"""
        if path not in self.giStatusByPath or self.giStatusByPath[path] != jmsg:
            self.giStatusByPath[path] = jmsg
            self.giStatusByPath.move_to_end(path)
            self.sendGameStatusToAll(path)

    def postProcessConnect(self, ws):
        # Notify of all ongoing game instances
        for path in self.giStatusByPath:
            self.sendGameStatusToOne(path, ws)

    def processHost(self, hostMsg):
        """Process the MTYPE_HOST message.
        hostMsg=[ MTYPE_HOST, <path>, <details> ]
        """
        self.txQueue.put_nowait(InternalHost(hostMsg.jmsg[2:],
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

def plugin(): # pylint: disable=missing-function-docstring
    return LobbyPlugin(LOBBY_PATH, "Main lobby")
