"""Classes that can be reused across many
game instances. Game instance specific
data should be passed in to methods but
not retained locally.
"""

from Dirty7 import Card
from Dirty7 import Dirty7Round
from Dirty7.Events import (
        AdvanceTurn,
        Declare,
)
from Dirty7.Exceptions import InvalidPlayException
from fwk.Trace import (
        Level,
        trace,
)

###########################################################
# Move validators and processors

class MoveProcessor:
    def __init__(self, ruleName, minCardCount=1, maxCardCount=None):
        self.ruleName = ruleName
        self.minCardCount = minCardCount
        self.maxCardCount = maxCardCount

    def makePlay(self, tableCards, playerHand, dropCards, numDrawCards, pickCards):
        gainCards = tableCards.delta(dropCards, pickCards, numDrawCards)
        playerHand.delta(dropCards, gainCards)


    def validatePlay(self, round_, player, dropCards, numDrawCards, pickCards):
        raise NotImplementedError

    def processPlay(self, round_, player, dropCards, numDrawCards, pickCards):
        """Returns None if the play message was not processed.
        If it is handled, return an Event type.
        """
        trace(Level.play, self.ruleName, "player", player.name,
              "dropCards", list(map(str, dropCards)),
              "numDrawCards", numDrawCards,
              "pickCards", list(map(str, pickCards)))

        # Must drop at least one card
        if not dropCards:
            trace(Level.debug, "Must drop some cards")
            return None

        # Apply move processor specific validation
        if not self.validatePlay(round_, player, dropCards, numDrawCards, pickCards):
            return None

        playerRoundStatus = round_.playerRoundStatus[player.name]
        if not playerRoundStatus.hand.contains(dropCards):
            trace(Level.debug, "Playing cards not in the hand {}".format(list(map(str, dropCards))))
            return None

        # self.minCardCount .. self.maxCardCount check
        dropCardCount = len(dropCards)

        if self.minCardCount is not None and dropCardCount < self.minCardCount:
            trace(Level.debug, "Must drop at least {} cards".format(self.minCardCount))
            return None

        if self.maxCardCount is not None and dropCardCount > self.maxCardCount:
            trace(Level.debug, "Can drop at most {} cards".format(self.maxCardCount))
            return None

        # Can't pick and draw at the same time
        if numDrawCards > 0 and len(pickCards) > 0:
            trace(Level.debug, "Can't draw cards and pick cards at the same time")
            return None

        # Must pick or draw a card
        if numDrawCards == 0 and pickCards == []:
            trace(Level.debug, "Must draw a card or pick a card")
            return None

        # Can draw only 1 card
        if numDrawCards != 1 and len(pickCards) == 0:
            trace(Level.debug, "Must draw only 1 card")
            return None

        tableCards = round_.tableCards

        # pickCards must be of length 1 and be visible
        if numDrawCards == 0 and len(pickCards) > 1:
            trace(Level.debug, "Must pick only 1 card")
            return None

        ## The move is valid. Make it happen

        self.makePlay(tableCards, playerRoundStatus.hand, dropCards, numDrawCards, pickCards)

        return AdvanceTurn(1)


class SameRankMove(MoveProcessor):
    """Allows the play of 1 or more cards of the same rank"""

    def __init__(self, minCardCount=1, maxCardCount=None):
        super(SameRankMove, self).__init__("SameRankMove",
                                           minCardCount=minCardCount,
                                           maxCardCount=maxCardCount)

    def validatePlay(self, round_, player, dropCards, numDrawCards, pickCards):
        # All dropCards should have the same rank
        if len(set(card.rank for card in dropCards)) > 1:
            trace(Level.debug, "All cards must have the same rank")
            return False

        return True

class SeqMove(MoveProcessor):
    """Allows the play of sequence of cards. The sequence must be
    of length minCardCount..maxCardCount
    """
    def __init__(self, minCardCount=1, maxCardCount=None):
        super(SeqMove, self).__init__("SeqMove[{},{}]".format(minCardCount, maxCardCount),
                                      minCardCount=minCardCount,
                                      maxCardCount=maxCardCount)

    def validatePlay(self, round_, player, dropCards, numDrawCards, pickCards):
        # Cards played must have exactly 1 card of each rank
        ranksSeen = [card.rank for card in dropCards]
        if len(ranksSeen) != len(set(ranksSeen)):
            trace(Level.debug, "Duplicate cards played")
            return False

        # Ensure the cards are in a sequence
        ranksSeen = sorted(ranksSeen)
        if ranksSeen != list(range(ranksSeen[0], ranksSeen[0] + len(ranksSeen))):
            trace(Level.debug, "Cards not in a sequence")
            return False

        return True

class SameSuitMove(MoveProcessor):
    """Allows the play of cards of the same suit. Joker can match any suit.
    The sequence must be of length minCardCount..maxCardCount
    """
    def __init__(self, minCardCount=1, maxCardCount=None):
        super(SameSuitMove, self).__init__("SameSuitMove[{},{}]".format(minCardCount, maxCardCount),
                                           minCardCount=minCardCount,
                                           maxCardCount=maxCardCount)

    def validatePlay(self, round_, player, dropCards, numDrawCards, pickCards):
        # Cards played must have exactly 1 suit (and jokers)
        suitsSeen = set(card.suit for card in dropCards) - {Card.JOKER}
        if len(suitsSeen) > 1:
            trace(Level.debug, "More than 1 suit is played")
            return False

        return True

###########################################################
# Rule engines

class RuleEngine:
    def __init__(self, shortName, name, moveProcessorList):
        """
        Arguments
        ---------
        shortName : str (Internal name of the rule)
        name : str (User facing name for the rule engine)
        moveProcessorList : list of MoveProcessor
        """
        self.shortName = shortName
        self.name = name
        self.moveProcessorList = moveProcessorList

    def cardPoints(self, card):
        return min(card.rank, 10)

    def makeRoundParameters(self, hostParams, roundNum):
        roundParameters = Dirty7Round.RoundParameters(
            [self.shortName],
            hostParams.numPlayers,
            hostParams.state.numDecks,
            hostParams.state.numJokers,
            hostParams.state.numCardsToStart,
            hostParams.state.declareMaxPoints,
            hostParams.state.penaltyPoints,
            hostParams.state.stopPoints,
            roundNum=roundNum)
        return roundParameters

    def processDeclare(self, round_, player):
        """
        If declareMaxPoints is specified, make sure that the person
        declaring has points <= declareMaxPoints.

        Return Declare() event if it is a valid declare, None otherwise.
        """
        roundParams = round_.roundParams
        playerRoundStatus = round_.playerRoundStatus[player.name]
        playerHand = playerRoundStatus.hand
        handScore = playerHand.score(self)

        if (roundParams.declareMaxPoints and
                handScore > roundParams.declareMaxPoints):
            trace(Level.info, "Declaring with", handScore, "points >",
                  roundParams.declareMaxPoints, "points.",
                  [str(cd) for cd in playerHand.cards])
            return None

        # Points are sufficiently low
        return Declare(player, handScore)

    def processPlay(self, round_, player, dropCards, numDrawCards, pickCards):
        """On valid play, make the change thru round_ and have that generate the
        required notification messages.
        If the move is invalid, return None

        Returns : EVENT (such as AdvanceTurn)
        """
        for moveProcessor in self.moveProcessorList:
            result = moveProcessor.processPlay(round_, player,
                                               dropCards,
                                               numDrawCards,
                                               pickCards)
            if result is not None:
                return result

        return None

#* ruleSet = subset from
#     {"random",
#      "basic",
#      "basic-10card",
#      "pick-any",
#      "seq3",
#      "seq3+",
#      "declare-any",
#      "hearts-1",
#      "one-or-seq3",
#      "one-or-seq3+",
#      "flush4"}

###########################################################

class Basic(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "basic", "Basic rules",
                            [SameRankMove()])

class BasicSeq3(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "basic,seq3", "Basic + sequence of 3 rules",
                            [SameRankMove(),
                             SeqMove(minCardCount=3, maxCardCount=3)])

class BasicSeq3Plus(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "basic,seq3+", "Basic + sequence of 3 or more rules",
                            [SameRankMove(),
                             SeqMove(minCardCount=3, maxCardCount=None)])

class BasicSuit3(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "basic,suit3", "Basic + flush of 3 rules",
                            [SameRankMove(),
                             SameSuitMove(minCardCount=3, maxCardCount=3)])

class BasicSuit3Plus(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "basic,suit3+", "Basic + flush of 3 or more rules",
                            [SameRankMove(),
                             SameSuitMove(minCardCount=3, maxCardCount=None)])

class Seq3(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "seq3", "Sequence of 3 rules",
                            [SameRankMove(maxCardCount=1),
                             SeqMove(minCardCount=3, maxCardCount=3)])

class Seq3Plus(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "seq3+", "Sequence of 3 or more rules",
                            [SameRankMove(maxCardCount=1),
                             SeqMove(minCardCount=3, maxCardCount=None)])

class Suit3(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "suit3", "Flush of 3 rules",
                            [SameRankMove(maxCardCount=1),
                             SameSuitMove(minCardCount=3, maxCardCount=3)])

class Suit3Plus(RuleEngine):
    def __init__(self):
        RuleEngine.__init__(self, "suit3+", "Flush of 3+ rules",
                            [SameRankMove(maxCardCount=1),
                             SameSuitMove(minCardCount=3, maxCardCount=None)])

SupportedRules = {re.shortName: re for re in
                  (Basic(),
                   BasicSeq3(),
                   BasicSeq3Plus(),
                   BasicSuit3(),
                   BasicSuit3Plus(),
                   Seq3(),
                   Seq3Plus(),
                   Suit3(),
                   Suit3Plus(),
                  )}
