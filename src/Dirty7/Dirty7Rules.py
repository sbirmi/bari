"""Classes that can be reused across many
game instances. Game instance specific
data should be passed in to methods but
not retained locally.
"""

class MoveProcessor:
    def processJmsg(self, rule, round_, jmsg):
        """Returns True if the message was processed,
        else returns False
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
