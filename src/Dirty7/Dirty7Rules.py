"""Classes that can be reused across many
game instances. Game instance specific
data should be passed in to methods but
not retained locally.
"""

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
    ruleName = None

    def makePlay(self, tableCards, playerHand, dropCards, numDrawCards, pickCards):
        gainCards = tableCards.delta(dropCards, pickCards, numDrawCards)
        playerHand.delta(dropCards, gainCards)

    def processPlay(self, round_, player, dropCards, numDrawCards, pickCards):
        """Returns None if the play message was not processed.
        If it is handled, return an Event type.
        """
        raise NotImplementedError


class SameRank(MoveProcessor):
    """Allows the play of 1 or more cards of the same rank"""
    ruleName = "SameRank"

    def __init__(self, minCardCount=1, maxCardCount=None):
        self.minCardCount = minCardCount
        self.maxCardCount = maxCardCount

    def processPlay(self, round_, player, dropCards, numDrawCards, pickCards):
        trace(Level.play, self.ruleName, "player", player.name,
              "dropCards", list(map(str, dropCards)),
              "numDrawCards", numDrawCards,
              "pickCards", list(map(str, pickCards)))

        # Must drop at least one card
        if not dropCards:
            trace(Level.debug, "Must drop some cards")
            return None

        # All dropCards should have the same rank
        if len(set(card.rank for card in dropCards)) > 1:
            trace(Level.debug, "All cards must have the same rank")
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
    def __init__(self, moveProcessorList):
        RuleEngine.__init__(self, "basic", "Basic rules",
                            moveProcessorList)

class Seq3(RuleEngine):
    def __init__(self, moveProcessorList):
        RuleEngine.__init__(self, "basic", "Basic rules",
                            moveProcessorList)

SupportedRules = {re.shortName: re for re in
                  (Basic([SameRank()]),
                   Seq3([SameRank()]),
                  )}
