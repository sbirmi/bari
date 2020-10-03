"""Classes that can be reused across many
game instances. Game instance specific
data should be passed in to methods but
not retained locally.
"""

from Dirty7 import Dirty7Round

class MoveProcessor:
    def processPlay(self, round_, player, dropCards, numDrawCards, pickCards):
        """Returns None if the play message was not processed.
        If it is handled, return an Event type.

        If the move is invalid, return InvalidPlayException.
        """
        raise NotImplementedError

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

    def processPlay(self, round_, player, dropCards, numDrawCards, pickCards):
        """On valid play, make the change thru round_ and have that generate the
        required notification messages.
        If the move is invalid, raise InvalidPlayException(<str>)

        Returns : EVENT (such as AdvanceTurn)
        """
        for moveProcessor in self.moveProcessorList:
            result = moveProcessor.processPlay(round_, player,
                                               dropCards,
                                               numDrawCards,
                                               pickCards)
            if result:
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
        moveProcessorList = []
        RuleEngine.__init__(self, "basic", "Basic rules",
                            moveProcessorList)

class Seq3(RuleEngine):
    def __init__(self):
        moveProcessorList = []
        RuleEngine.__init__(self, "basic", "Basic rules",
                            moveProcessorList)

SupportedRules = {re.shortName: re for re in
                  (Basic(),
                   Seq3(),
                  )}
