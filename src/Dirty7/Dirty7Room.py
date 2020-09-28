"""Dirty7 game instance"""

from fwk.GamePlugin import GamePlugin
from fwk.Msg import InternalGiStatus

class Dirty7Room(GamePlugin):
    def __init__(self, path, name, hostParameters):
        GamePlugin.__init__(self, path, name)
        self.hostParameters = hostParameters

    def processMsg(self, qmsg):
        if super(Dirty7Room, self).processMsg(qmsg):
            return True
        return False

    def publishGiStatus(self):
        pass
#        # Publish number of clients connected to this room
#        self.txQueue.put_nowait(InternalGiStatus(
#            [{"clients": self.conns.count()}], self.path))
