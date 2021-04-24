"""Taboo room"""

from fwk.GamePlugin import GamePlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)
from Taboo.HostParametersMsgSrc import HostParametersMsgSrc

class TabooRoom(GamePlugin):
    def __init__(self, path, name, hostParameters):
        super(TabooRoom, self).__init__(path, name)
        self.hostParameters = hostParameters

        self.hostParametersMsgSrc = None

    def init_game(self):
        self.hostParametersMsgSrc = HostParametersMsgSrc(self.conns, self.hostParameters)

    def publishGiStatus(self):
        """Invoked to update the lobby of the game instance (room) status

               ["GAME-STATUS", <path:str>, {"gameState": <str>,
                                            "clientCount": <str>,
                                            "spectatorCount": <int>,
                                            "hostParams": <dict>}]
        """
        jmsg = [{"hostParameters": self.hostParameters.toJmsg()[0],
                 "clientCount": self.conns.count()}]
        self.txQueue.put_nowait(InternalGiStatus(jmsg, self.path))

    def postQueueSetup(self):
        """Invoked when the RX+TX queues are set up to the room and
        when the self.conns object is setup to track all clients in the room
        """
        self.init_game()
        self.publishGiStatus()

    def postProcessConnect(self, ws):
        """Invoked when a new client (websocket) connects from the room.
        Note that no messages have been exchanged yet
        """
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        """Invoked when a client disconnects from the room"""
        self.publishGiStatus()

    def processMsg(self, qmsg):
        """Handle messages from the queue coming to this room"""
        if super(TabooRoom, self).processMsg(qmsg):
            return True

        return False
