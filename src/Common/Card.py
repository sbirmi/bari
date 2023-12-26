from fwk.Exceptions import InvalidDataException
from fwk.MsgSrc import MsgSrc

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

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        if self.suit == "JOKER":
            return "JOKER"
        return "{}{}".format(self.rank, self.suit)

    @staticmethod
    def deckCards(numDecks=0):
        for _ in range(numDecks):
            for suit in (CLUBS, DIAMONDS, HEARTS, SPADES):
                for rank in range(1, 14):
                    yield Card(suit, rank)

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
            if jmsgs is not None:
                self.connsMsgSrc.setMsgs(jmsgs)

        if self.playerConnsMsgSrc:
            jmsgs = self._playerConnsJmsgs()
            if jmsgs is not None:
                self.playerConnsMsgSrc.setMsgs(jmsgs)

    def _connsJmsgs(self):
        raise NotImplementedError

    def _playerConnsJmsgs(self):
        raise NotImplementedError

    @staticmethod
    def contains(cards1, cards2):
        """Returns cards1 contains cards2"""
        cards1_ = cards1[:]
        for card in cards2:
            try:
                idx = cards1_.index(card)
            except ValueError:
                return False
            cards1_.pop(idx)

        return True
