"""Round specific details are tracked in classes
defined here.
"""

from fwk.Common import Map

from fwk.MsgSrc import MsgSrc
from Dirty7.Card import CardGroupBase
from Dirty7.Dirty7Rules import SupportedRules
from Dirty7.Exceptions import InvalidDataException

class Round:
    def __init__(self, conns, ruleEngine, roundNum, roundParams,
                 isRoundOver=False):
        self.conns = conns
        self.roundNum = roundNum
        self.roundParams = roundParams
        self.ruleEngine = ruleEngine
        self.roundScore = RoundScore(conns, roundNum)
        self.playerRoundStatus = {}
        self.playerNameInTurnOrder = []
        self.turnIdx = 0
        self.tableCards = TableCards(conns, roundNum)
        self.isRoundOver = isRoundOver

class RoundParameters:
    ctrArgs = ("ruleNames",
               "numPlayers",
               "numDecks",
               "numJokers",
               "numCardsToStart",
               "declareMaxPoints",
               "penaltyPoints",
               "stopPoints")

    def __init__(self,
                 ruleNames,
                 numPlayers,
                 numDecks,
                 numJokers,
                 numCardsToStart,
                 declareMaxPoints,
                 penaltyPoints,
                 stopPoints):
        self.msgSrc = None
        self.roundNum = None

        if (not isinstance(ruleNames, (list, set)) or
                len(ruleNames) != 1 or
                next(iter(ruleNames)) not in SupportedRules):
            raise InvalidDataException("Invalid names of rules", ruleNames)

        if not numDecks in {1, 2}:
            raise InvalidDataException("Invalid number of decks", numDecks)

        if not numJokers in range(2 * numDecks):
            raise InvalidDataException("Invalid number of jokers", numJokers)

        if not numPlayers in range(1, 9):
            raise InvalidDataException("Invalid number of players", numPlayers)

        if numCardsToStart not in range(3, 14):
            raise InvalidDataException("Invalid number of cards to deal", numCardsToStart)

        if numCardsToStart * numPlayers + 1 >= numDecks * 52 + numJokers:
            raise InvalidDataException("Too many cards to deal", numCardsToStart)

        if not isinstance(declareMaxPoints, int) or declareMaxPoints <= 0:
            raise InvalidDataException("Invalid declareMaxPoints", declareMaxPoints)

        if not isinstance(penaltyPoints, int) or penaltyPoints < 20:
            raise InvalidDataException("Invalid penalty points or too low", penaltyPoints)

        if not isinstance(stopPoints, int) or stopPoints < 0:
            raise InvalidDataException("Invalid stopPoints", stopPoints)

        self.state = Map(ruleName=ruleNames,
                         numPlayers=numPlayers,
                         numDecks=numDecks,
                         numJokers=numJokers,
                         numCardsToStart=numCardsToStart,
                         declareMaxPoints=declareMaxPoints,
                         penaltyPoints=penaltyPoints,
                         stopPoints=stopPoints)
        self.ruleEngine = SupportedRules[next(iter(ruleNames))]

    def setPostInitParams(self, conns, roundNum):
        assert not self.msgSrc
        self.roundNum = roundNum
        self.msgSrc = MsgSrc(conns)
        self.msgSrc.setMsgs([["ROUND-PARAMETERS", self.roundNum, dict(self.state)]])

    @staticmethod
    def fromJmsg(jmsg):
        if not isinstance(jmsg, list) or len(jmsg) != len(RoundParameters.ctrArgs):
            raise InvalidDataException("Invalid round parameters type or length", jmsg)

        return RoundParameters(**dict(zip(RoundParameters.ctrArgs, jmsg)))


class RoundScore(MsgSrc):
    """Tracks the score of all players at the end of the round"""
    def __init__(self, conns, roundNum, scoreByPlayerName=None):
        MsgSrc.__init__(self, conns)
        self.roundNum = roundNum
        self.scoreByPlayerName = None
        self.setScores(scoreByPlayerName or {})

    def setScores(self, scoreByPlayerName):
        self.scoreByPlayerName = scoreByPlayerName
        if self.scoreByPlayerName:
            self.setMsgs([["ROUND-SCORE", self.roundNum, self.scoreByPlayerName]])

class TableCards(CardGroupBase):
    def __init__(self, conns, roundNum,
                 deckCards=None,
                 revealedCards=None,
                 hiddenCards=None):
        self.roundNum = roundNum
        self.deckCards = deckCards
        self.hiddenCards = hiddenCards
        self.revealedCards = revealedCards
        CardGroupBase.__init__(self, conns, playerConns=None)

    def _connsJmsgs(self):
        if (self.deckCards is None or self.revealedCards is None or
                self.hiddenCards is None):
            return None

        return ["TABLE-CARDS", self.roundNum,
                len(self.deckCards),
                len(self.hiddenCards),
                [card.toJmsg() for card in self.revealedCards]]

    def _playerConnsJmsgs(self):
        return None

class PlayerRoundStatus:
    def __init__(self, conns, player):
        self.conns = conns
        self.player = player
        self.hand = PlayerHand(self.conns,
                               self.player.playerConns,
                               self.player.roundNum,
                               self.player.name)

class PlayerHand(CardGroupBase):
    def __init__(self, conns, playerConns, roundNum, playerName,
                 cards=None,
                 isRoundOver=False):
        self.roundNum = roundNum
        self.playerName = playerName
        self.cards = cards
        self.isRoundOver = isRoundOver
        CardGroupBase.__init__(self, conns, playerConns)

    def setCards(self, cards):
        self.cards = cards
        self.refresh()

    def roundOver(self):
        """Reveals the hand to all players"""
        self.isRoundOver = True
        self.refresh()

    def _connsJmsgs(self):
        if self.cards is None:
            return None

        if self.isRoundOver:
            return [["PLAYER-CARDS", self.roundNum,
                     self.playerName, len(self.cards),
                     [card.toJmsg() for card in self.cards]]]

        return [["PLAYER-CARDS", self.roundNum,
                 self.playerName, len(self.cards)]]

    def _playerConnsJmsgs(self):
        if self.cards is None:
            return None

        if self.isRoundOver:
            # Nothing to do here. We will reveal the full
            # hand to all in _setConnsData
            return None

        return [["PLAYER-CARDS", self.roundNum,
                 self.playerName, len(self.cards),
                 [card.toJmsg() for card in self.cards]]]
