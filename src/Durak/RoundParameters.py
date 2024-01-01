from fwk.Common import Map
from fwk.Exceptions import InvalidDataException
from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)

class RoundParameters:
    ctrArgs = ("numPlayers",
               "stopPoints",
              )
    def __init__(self,
                 numPlayers,
                 stopPoints,
                 numDecks=1,
                 numCardsToStart=6,
                 roundNum=0):
        self.msgSrc = None
        self.roundNum = roundNum

        if not isinstance(numPlayers, int):
            raise InvalidDataException("Invalid number of players: integer expected", numPlayers)

        if not isinstance(stopPoints, int):
            raise InvalidDataException("Invalid stopping points: integer expected", stopPoints)

        if numPlayers < 2 or numPlayers > 10:
            raise InvalidDataException("Invalid number of players: number too large or too small",
                                       numPlayers)

        if numDecks * 52 - numPlayers * numCardsToStart < 16:
            raise InvalidDataException(f"Too many players to host with {numDecks} decks",
                                       numPlayers)

        vals = locals()
        self.state = Map(**{argName: vals[argName] for argName in self.ctrArgs})

    def __getattr__(self, name):
        """Convenience accessors for attributes in self.state"""
        return getattr(self.state, name)

    def setPostInitParams(self, conns, roundNum):
        assert not self.msgSrc
        self.roundNum = roundNum
        self.msgSrc = MsgSrc(conns)
        self.msgSrc.setMsgs([Jmai(["ROUND-PARAMETERS", self.roundNum, dict(self.state)], None)])

    @staticmethod
    def fromJmsg(jmsg):
        if not isinstance(jmsg, list) or len(jmsg) != 1 or not isinstance(jmsg[0], dict):
            raise InvalidDataException("Invalid host parameters type or length", jmsg)

        if set(jmsg[0]) != set(RoundParameters.ctrArgs):
            raise InvalidDataException("Invalid or unexpected host parameters keys", jmsg)

        return RoundParameters(**jmsg[0])

    def toJmsg(self):
        return [dict(self.state)]

#1. Number of players: 2..6
#2. numDecks = 1
#3. numJokers = 0
#4. Stop criteria (first to lose N rounds) = 5
#5. Trump { "random" }
