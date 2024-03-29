from fwk.MsgSrc import (
        Connections,
        Jmai,
        MsgSrc,
)

from Common.Card import cardListContains

class Player:
    def __init__(self, txQueue, allConns, name):
        """Creates a player

        txQueue: tx queue
        allConns: Connections with all clients in the room
        name: player name
        """
        self.name = name

        self.playerConns = Connections(txQueue)
        self.hand = PlayerHand(allConns, self.playerConns,
                               self.name)

        self.playerStatusMsgSrc = MsgSrc(allConns)

    def cardCount(self):
        return len(self.hand.cards)

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

class PlayerHand:
    """
    ["PLAYER-HAND", name, numCards, cards (optional)]
    """
    def __init__(self, allConns, playerConns, name):
        self.name = name
        self.cards = []

        self.broadcastMsgSrc = MsgSrc(allConns)
        self.playerMsgSrc = MsgSrc(playerConns)

    def resetCards(self):
        self.cards = []
        self.refresh()

    def setCards(self, cards):
        self.cards = cards
        self.refresh()

    def hasCards(self, cards):
        return cardListContains(self.cards, cards)

    def removeCards(self, cards):
        for card in cards:
            idx = self.cards.index(card)
            self.cards.pop(idx)

        self.refresh()

    def addCards(self, cards):
        self.cards.extend(cards)
        self.refresh()

    def refresh(self):
        msg = ["PLAYER-HAND",
               self.name,
               len(self.cards)]
        self.broadcastMsgSrc.setMsgs([
            Jmai(msg[:], None),
        ])

        msg += [[card.toJmsg() for card in self.cards],]
        self.playerMsgSrc.setMsgs([
            Jmai(msg, None),
        ])
