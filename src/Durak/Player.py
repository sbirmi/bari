from fwk.MsgSrc import (
        Connections,
        Jmai,
        MsgSrc,
)

class Player:

    def __init__(self, txQueue, allConns, name):
        """Creates a player

        txQueue: tx queue
        allConns: Connections with all clients in the room
        name: player name
        """
        self.name = name

        self.playerConns = Connections(txQueue)

        self.playerStatusMsgSrc = MsgSrc(allConns)

    def __str__(self):
        return f"Durak player={self.name}"

    def addConn(self, ws):
        self.playerConns.addConn(ws)
        self._updateMsgSrc()

    def delConn(self, ws):
        self.playerConns.delConn(ws)
        self._updateMsgSrc()

    def numConns(self):
        return self.playerConns.count()

    def _updateMsgSrc(self):
        self.playerStatusMsgSrc.setMsgs([
            Jmai(["PLAYER-STATUS", self.name, self.numConns()], None),
        ])
