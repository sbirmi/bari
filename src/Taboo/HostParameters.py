from fwk.Common import Map
from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)
from fwk.Exceptions import InvalidDataException
from Taboo.WordSets import SupportedWordSets

MIN_TEAMS = 1
MAX_TEAMS = 4

MIN_TURN_DURATION = 30
MAX_TURN_DURATION = 180

class HostParameters:
    """Tracks host parameters for a game

    The actual data is stored in self.state (a Map -- a glorified dictionary)
    Since this object is usually constructed from client side, validation is
    explicitly done and InvalidDataException is raised on error which is passed
    back to the client trying to host the game.

    The object embeds a MsgSrc (self.msgSrc) which is used to emit host parameters
    to every client of the hosted room (once the room is created). This is initialized
    by calling setPostInitParams() after the game room is created.
    """
    ctrArgs = ("numTeams",
               "turnDurationSec",
               "wordSets",
               "allowLateJoinees",
              )

    def __init__(self,
                 numTeams,
                 turnDurationSec,
                 wordSets,
                 allowLateJoinees):
        self.msgSrc = None

        if not isinstance(numTeams, int) or numTeams < MIN_TEAMS or numTeams > MAX_TEAMS:
            raise InvalidDataException("Invalid type or numTeams", numTeams)

        if (not isinstance(turnDurationSec, int) or turnDurationSec < MIN_TURN_DURATION or
                turnDurationSec > MAX_TURN_DURATION):
            raise InvalidDataException("Invalid type or turnDurationSec", turnDurationSec)

        if (not isinstance(wordSets, list) or not wordSets or
                not set(wordSets).issubset(SupportedWordSets)):
            raise InvalidDataException("Invalid type or wordSets", wordSets)

        if not isinstance(allowLateJoinees, bool):
            raise InvalidDataException("Invalid type or allowLateJoinees", allowLateJoinees)

        self.state = Map(numTeams=numTeams,
                         turnDurationSec=turnDurationSec,
                         wordSets=wordSets,
                         allowLateJoinees=allowLateJoinees)

    def __getattr__(self, name):
        """When access hostParameters.numTeams, fetch it from self.state instead"""
        return getattr(self.state, name)

    def setPostInitParams(self, conns):
        assert not self.msgSrc
        self.msgSrc = MsgSrc(conns)
        # Set the message to be sent to all clients in conns
        self.msgSrc.setMsgs([Jmai(["HOST-PARAMETERS", dict(self.state)], None)])

    @staticmethod
    def fromJmsg(jmsg):
        if not isinstance(jmsg, list) or len(jmsg) != 1 or not isinstance(jmsg[0], dict):
            raise InvalidDataException("Invalid host parameters type or length", jmsg)

        if set(jmsg[0]) != set(HostParameters.ctrArgs):
            raise InvalidDataException("Invalid or unexpected host parameters keys", jmsg)

        return HostParameters(**jmsg[0])

    def toJmsg(self):
        return [dict(self.state)]
