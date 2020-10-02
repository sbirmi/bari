"""Round specific details are tracked in classes
defined here.
"""

import random

from fwk.Common import Map

from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)
from Dirty7.Card import (
        CLUBS,
        DIAMONDS,
        HEARTS,
        SPADES,
        JOKER,
        Card,
        CardGroupBase,
)
from Dirty7.Dirty7Rules import SupportedRules
from Dirty7.Exceptions import InvalidDataException

class Turn(MsgSrc):
    """Tracks turn order and whose turn it is"""
    def __init__(self, conns, roundNum, playerNames):
        MsgSrc.__init__(self, conns)
        self.roundNum = roundNum
        self.playerNameInTurnOrder = playerNames
        self.numPlayers = len(self.playerNameInTurnOrder)
        random.shuffle(self.playerNameInTurnOrder)
        self.turnIdx = 0

        jmsg1 = ["TURN-ORDER", self.roundNum, self.playerNameInTurnOrder]
        jmsg2 = ["TURN", self.roundNum, self.current()]
        self.setMsgs([Jmai(jmsg1, None), Jmai(jmsg2, None)])

    def next(self):
        self.turnIdx = (self.turnIdx + 1) % self.numPlayers
        jmsg = ["TURN", self.roundNum, self.current()]
        self.replaceMsg(1, jmsg)

    def current(self):
        return self.playerNameInTurnOrder[self.turnIdx]


class Round:
    def __init__(self, path, conns, roundParams,
                 playerByName,
                 playerByWs,
                 isRoundOver=False):
        assert len(roundParams.state.ruleNames) == 1

        self.path = path
        self.conns = conns
        self.roundParams = roundParams
        self.playerByName = playerByName
        self.playerByWs = playerByWs
        self.isRoundOver = isRoundOver

        self.turn = Turn(conns, roundParams.roundNum, list(playerByName))
        self.roundScore = RoundScore(conns, roundParams.roundNum,
                                     {name: None for name in self.playerByName})

        deckCards = roundParams.createStartingCards()

        self.playerRoundStatus = {}
        for name, player in self.playerByName.items():
            handCards = [deckCards.pop() for _ in range(roundParams.numCardsToStart)]
            self.playerRoundStatus[name] = PlayerRoundStatus(
                conns,
                roundParams.roundNum,
                player,
                handCards)

        revealedCards = [deckCards.pop()]

        self.tableCards = TableCards(conns, roundParams.roundNum,
                                     deckCards=deckCards,
                                     revealedCards=revealedCards)

        self.rule = SupportedRules[next(iter(roundParams.state.ruleNames))]

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
                 stopPoints,
                 roundNum=0):
        self.msgSrc = None
        self.roundNum = roundNum

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

        self.state = Map(ruleNames=ruleNames,
                         numPlayers=numPlayers,
                         numDecks=numDecks,
                         numJokers=numJokers,
                         numCardsToStart=numCardsToStart,
                         declareMaxPoints=declareMaxPoints,
                         penaltyPoints=penaltyPoints,
                         stopPoints=stopPoints)
        self.ruleEngine = SupportedRules[next(iter(ruleNames))]

    def __getattr__(self, name):
        return getattr(self.state, name)

    def setPostInitParams(self, conns, roundNum):
        assert not self.msgSrc
        self.roundNum = roundNum
        self.msgSrc = MsgSrc(conns)
        self.msgSrc.setMsgs([Jmai(["ROUND-PARAMETERS", self.roundNum, dict(self.state)], None)])

    @staticmethod
    def fromJmsg(jmsg):
        if not isinstance(jmsg, list) or len(jmsg) != len(RoundParameters.ctrArgs):
            raise InvalidDataException("Invalid round parameters type or length", jmsg)

        return RoundParameters(**dict(zip(RoundParameters.ctrArgs, jmsg)))

    def toJmsg(self):
        return [self.roundNum, dict(self.state)]

    def roundParameters(self, roundNum):
        """Create round parameters from hostParameters"""
        ruleName = random.choice(self.state.ruleNames)
        return SupportedRules[ruleName].makeRoundParameters(self, roundNum)

    def createStartingCards(self):
        cards = []
        for rank in range(1, 14):
            cards.extend([Card(suit, rank) for suit in (CLUBS, DIAMONDS, HEARTS, SPADES)])
        cards = cards * self.numDecks
        cards.extend([Card(JOKER, 0) for _ in range(self.numJokers)])
        random.shuffle(cards)
        return cards

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
            self.setMsgs([Jmai(["ROUND-SCORE", self.roundNum, self.scoreByPlayerName], None)])

class TableCards(CardGroupBase):
    def __init__(self, conns, roundNum,
                 deckCards=None,
                 revealedCards=None,
                 hiddenCards=None):
        self.roundNum = roundNum
        self.deckCards = deckCards
        self.revealedCards = revealedCards
        self.hiddenCards = hiddenCards or []
        CardGroupBase.__init__(self, conns, playerConns=None)

    def _connsJmsgs(self):
        if (self.deckCards is None or self.revealedCards is None or
                self.hiddenCards is None):
            return None

        return [Jmai(["TABLE-CARDS", self.roundNum,
                      len(self.deckCards), len(self.hiddenCards),
                      [card.toJmsg() for card in self.revealedCards]], None)]

    def _playerConnsJmsgs(self):
        return None

class PlayerRoundStatus:
    def __init__(self, conns, roundNum, player, handCards):
        self.conns = conns
        self.roundNum = roundNum
        self.player = player
        self.hand = PlayerHand(self.conns,
                               self.player.playerConns,
                               roundNum,
                               self.player.name,
                               handCards)

class PlayerHand(CardGroupBase):
    def __init__(self, conns, playerConns, roundNum, playerName, cards,
                 isRoundOver=False):
        self.roundNum = roundNum
        self.playerName = playerName
        self.cards = None
        self.isRoundOver = isRoundOver
        CardGroupBase.__init__(self, conns, playerConns)
        self.setCards(cards)

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
            return [Jmai(["PLAYER-CARDS", self.roundNum,
                          self.playerName, len(self.cards),
                          [card.toJmsg() for card in self.cards]], None)]

        return [Jmai(["PLAYER-CARDS", self.roundNum,
                      self.playerName, len(self.cards)], None)]

    def _playerConnsJmsgs(self):
        if self.cards is None:
            return None

        if self.isRoundOver:
            # Nothing to do here. We will reveal the full
            # hand to all in _setConnsData
            return None

        return [Jmai(["PLAYER-CARDS", self.roundNum,
                      self.playerName, len(self.cards),
                      [card.toJmsg() for card in self.cards]], None)]
