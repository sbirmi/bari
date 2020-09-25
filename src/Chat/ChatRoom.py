"""Defines a chat room in bari"""

from fwk.GamePlugin import GamePlugin
from fwk.Msg import InternalGiStatus

class ChatRoom(GamePlugin):
    """Defines a chat room"""
    def processMsg(self, qmsg):
        if super(ChatRoom, self).processMsg(qmsg):
            return True

        self.broadcast(qmsg.jmsg, initiatorWs=qmsg.initiatorWs)
        return True

    def postProcessConnect(self, ws):
        # Publish GAME-STATUS with number of clients connected to this room
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        # Publish GAME-STATUS with number of clients connected to this room
        self.publishGiStatus()

    def publishGiStatus(self):
        # Publish number of clients connected to this room
        self.txQueue.put_nowait(InternalGiStatus(
            [{"clients": self.conns.count()}], self.path))
