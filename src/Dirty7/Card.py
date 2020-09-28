from fwk.MsgSrc import MsgSrc
from Dirty7.Exceptions import InvalidDataException

CLUBS = "C"
DIAMONDS = "D"
HEARTS = "H"
SPADES = "S"
JOKER = "JOKER"

class Card:
    def __init__(self, suit, rank):
        if suit not in {CLUBS, DIAMONDS,
                        HEARTS, SPADES, JOKER}:
            raise InvalidDataException("Bad card suit", suit)

        if rank not in {0, 1, 2, 3, 4, 5, 6, 7,
                        8, 9, 10, 11, 12, 13}:
            raise InvalidDataException("Bad card rank", rank)

        if suit == JOKER and rank != 0:
            raise InvalidDataException("Bad rank for a joker", rank)

        if suit != JOKER and rank == 0:
            raise InvalidDataException("Bad rank", rank)

        self.suit = suit
        self.rank = rank

    @staticmethod
    def fromJmsg(jmsg):
        if not isinstance(jmsg, list) or len(jmsg) != 2:
            raise InvalidDataException("Bad card description", jmsg)

        return Card(jmsg[0], jmsg[1])

    def toJmsg(self):
        return [self.suit, self.rank]

class CardGroupBase:
    """
    How cards are stored is not captured in CardGroupBase
    """
    def __init__(self, conns, playerConns):
        self.connsMsgSrc = MsgSrc(conns) if conns else None
        self.playerConnsMsgSrc = MsgSrc(playerConns) if playerConns else None
        self.refresh()

    def refresh(self):
        if self.connsMsgSrc:
            jmsgs = self._connsJmsgs()
            if jmsgs:
                self.connsMsgSrc.setMsgs(jmsgs)

        if self.playerConnsMsgSrc:
            jmsgs = self._playerConnsJmsgs()
            if jmsgs:
                self.playerConnsMsgSrc.setMsgs(jmsgs)

    def _connsJmsgs(self):
        raise NotImplementedError

    def _playerConnsJmsgs(self):
        raise NotImplementedError
