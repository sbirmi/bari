"""Round specific details are tracked in classes
defined here.
"""

from collections import defaultdict
import random

from fwk.Common import Map
from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)
from fwk.Trace import (
        Level,
        trace,
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

def removeCards(cards1, cards2):
    """returns cards1 - cards2"""
    for card in cards2:
        idx = cards1.index(card)
        cards1.pop(idx)

class Turn(MsgSrc):
    """Tracks turn order and whose turn it is"""
    def __init__(self, conns, roundNum, playerNameInTurnOrder, turnIdx,
                 isRoundOver=False):
        MsgSrc.__init__(self, conns)
        self.roundNum = roundNum
        self.playerNameInTurnOrder = playerNameInTurnOrder
        self.numPlayers = len(self.playerNameInTurnOrder)
        self.turnIdx = turnIdx
        self.isRoundOver = isRoundOver

        if not isRoundOver:
            jmsg1 = ["TURN-ORDER", self.roundNum, self.playerNameInTurnOrder]
            jmsg2 = ["TURN", self.roundNum, self.current()]
            self.setMsgs([Jmai(jmsg1, None), Jmai(jmsg2, None)])

    def advance(self, advanceTurn):
        self.turnIdx = (self.turnIdx + advanceTurn.turnStep) % self.numPlayers
        jmsg = Jmai(["TURN", self.roundNum, self.current()], initiatorWs=None)
        self.replaceMsg(1, jmsg)

    def current(self):
        return self.playerNameInTurnOrder[self.turnIdx]

    def makeRoundOver(self):
        self.isRoundOver = True
        self.setMsgs([])

class Round:
    def __init__(self, path, conns, roundParams,
                 playerByName,
                 turn,
                 isRoundOver=False):
        assert len(roundParams.state.ruleNames) == 1

        self.path = path
        self.conns = conns
        self.roundParams = roundParams
        self.playerByName = playerByName
        self.turn = turn
        self.isRoundOver = isRoundOver

        self.roundParametersAnnouncer = RoundParametersAnnouncer(conns, roundParams)

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

        self.roundScore = RoundScore(conns, roundParams.roundNum,
                                     {name: None for name in self.playerByName})

        self.rule = SupportedRules[next(iter(roundParams.state.ruleNames))]

    @property
    def roundNum(self):
        return self.roundParams.roundNum

    def makeRoundOver(self):
        # TurnOrder is marked as not-announcing
        # Table cards as not-announcing
        self.isRoundOver = True
        for prs in self.playerRoundStatus.values():
            prs.hand.makeRoundOver()
        self.turn.makeRoundOver()
        self.tableCards.makeRoundOver()

    def declare(self, event):
        playerScores = {name: prs.hand.score(self.rule)
                        for name, prs in self.playerRoundStatus.items()}
        scorePlayers = defaultdict(set)

        uniqueScores = sorted(playerScores.values())
        for name, score in playerScores.items():
            scorePlayers[score].add(name)

        if uniqueScores[0] < event.score or len(scorePlayers[event.score]) > 1:
            for name in scorePlayers[uniqueScores[0]]:
                playerScores[name] = 0
            playerScores[event.player.name] = self.roundParams.penaltyPoints
        else:
            playerScores[event.player.name] = 0

        self.roundScore.setScores(playerScores)

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
                next(iter(ruleNames)) not in SupportedRules):
            raise InvalidDataException("Invalid names of rules", ruleNames)

        if not numDecks in {1, 2}:
            raise InvalidDataException("Invalid number of decks. Must be 1 or 2", numDecks)

        maxJokers = 2 * numDecks
        if not numJokers in range(maxJokers + 1):
            raise InvalidDataException("Invalid number of jokers. "
                                       "Must be between 0..{}".format(maxJokers),
                                       numJokers)

        if not numPlayers in range(1, 9):
            raise InvalidDataException("Invalid number of players. Must be between 1..8",
                                       numPlayers)

        if numCardsToStart not in range(3, 14):
            raise InvalidDataException("Invalid number of cards to deal. Must be between 3..13",
                                       numCardsToStart)

        if numCardsToStart * numPlayers + 1 >= numDecks * 52 + numJokers:
            raise InvalidDataException("Not enough cards to deal to each player", numCardsToStart)

        if not isinstance(declareMaxPoints, int) or declareMaxPoints <= 0:
            raise InvalidDataException("Invalid points for declaring. Must be greater than 0",
                                       declareMaxPoints)

        if not isinstance(penaltyPoints, int) or penaltyPoints < 20:
            raise InvalidDataException("Invalid penalty points. Must be greater than equal to 20",
                                       penaltyPoints)

        if not isinstance(stopPoints, int) or stopPoints < 0:
            raise InvalidDataException("Invalid stopPoints. Most be greater than equal to 0",
                                       stopPoints)

        self.state = Map(ruleNames=ruleNames,
                         numPlayers=numPlayers,
                         numDecks=numDecks,
                         numJokers=numJokers,
                         numCardsToStart=numCardsToStart,
                         declareMaxPoints=declareMaxPoints,
                         penaltyPoints=penaltyPoints,
                         stopPoints=stopPoints)

        if self.roundNum == 0:
            self.ruleEngine = None
        else:
            assert len(ruleNames) == 1
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

class RoundParametersAnnouncer(MsgSrc):
    """Tracks the parameters of the current round"""
    def __init__(self, conns, roundParameters):
        MsgSrc.__init__(self, conns)
        self.roundParameters = roundParameters
        self.setMsgs([Jmai(["ROUND-PARAMETERS"] + roundParameters.toJmsg(), None)])

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
    """Manages the cards on the table:
    1. the Deck
    2. the revealed cards
    3. the hidden cards (face-up cards that are hidden)
    """
    def __init__(self, conns, roundNum,
                 deckCards=None,
                 revealedCards=None,
                 hiddenCards=None,
                 isRoundOver=False):
        self.roundNum = roundNum
        self.deckCards = deckCards
        self.revealedCards = revealedCards
        self.hiddenCards = hiddenCards or []
        self.isRoundOver = isRoundOver
        CardGroupBase.__init__(self, conns, playerConns=None)

    def makeRoundOver(self):
        self.isRoundOver = True
        self.refresh()

    def revealedCardsContains(self, cards):
        return CardGroupBase.contains(self.revealedCards, cards)

    def deckCardCount(self):
        return len(self.deckCards)

    def delta(self, dropCards, pickCards, numDrawCards):
        assert numDrawCards <= self.deckCardCount()

        playerGainCards = pickCards[:]
        # Remove cards from the deck
        for _ in range(numDrawCards):
            playerGainCards.append(self.deckCards.pop(0))

        # Remove picked cards from revealed cards
        removeCards(self.revealedCards, pickCards) # revealedCards is updated in place

        # Push remaining revealed cards to the hiddenCards
        self.hiddenCards.extend(self.revealedCards)

        # revealedCards <-- dropCards
        self.revealedCards = dropCards

        # Shuffle deck if needed
        if self.deckCardCount() == 0:
            trace(Level.info, self.roundNum, "rebuild deck")
            # Take all hidden cards
            self.deckCards = self.hiddenCards
            self.hiddenCards = []
            random.shuffle(self.deckCards)

        self.refresh()
        return playerGainCards

    def _connsJmsgs(self):
        if self.isRoundOver:
            return []

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

    def score(self, rule):
        return sum(rule.cardPoints(cd) for cd in self.cards)

    def setCards(self, cards):
        self.cards = cards
        self.refresh()

    def contains(self, cards): # pylint: disable=arguments-differ
        return CardGroupBase.contains(self.cards, cards)

    def makeRoundOver(self):
        """Reveals the hand to all players"""
        self.isRoundOver = True
        self.refresh()

    def delta(self, dropCards, gainCards):
        removeCards(self.cards, dropCards)
        self.cards += gainCards
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
