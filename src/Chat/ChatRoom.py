from fwk.GamePlugin import Plugin
from fwk.Msg import MsgToWs

class ChatRoom(Plugin):
    def processMsg(self, qmsg):
        if super(ChatRoom, self).processMsg(qmsg):
            return True

        for ws in self.ws:
            self.txQueue.put_nowait(MsgToWs(ws, qmsg.jmsg))

        return True
