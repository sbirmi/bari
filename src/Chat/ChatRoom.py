from fwk.GamePlugin import Plugin
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)

class ChatRoom(Plugin):
    def processMsg(self, qmsg):
        if super(ChatRoom, self).processMsg(qmsg):
            return True

        for toWs in self.ws:
            self.txQueue.put_nowait(ClientTxMsg(qmsg.jmsg, toWs,
                                                initiatorWs=qmsg.initiatorWs))

        return True

    def postProcessConnect(self, ws):
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        self.publishGiStatus()

    def queueSetupComplete(self):
        self.publishGiStatus()

    def publishGiStatus(self):
        self.txQueue.put_nowait(InternalGiStatus(
            [{"clients": len(self.ws)}], self.path))
