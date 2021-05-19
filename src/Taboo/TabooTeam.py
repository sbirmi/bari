""" Taboo Team"""

from fwk.MsgSrc import (
    Connections,
    Jmai,
    MsgSrc,
)
from fwk.Trace import (
    trace,
    Level,
)

class TabooTeam:
    """ Creates a team with a specified teamNumber

    """
    def __init__(self, txQueue, allConns, teamNumber):
        self.txQueue = txQueue
        self.teamNumber = teamNumber

        self.teamStatusMsgSrc = MsgSrc(allConns)

        self.members = {}
        self.conns = Connections(self.txQueue)
        self._updateMsgSrc()

    def _updateMsgSrc(self):
        self.teamStatusMsgSrc.setMsgs([
            Jmai(["TEAM-STATUS", self.teamNumber, list(self.members)], None),
        ])

    def addPlayer(self, player):
        """ Players need to be unique. Reset not allowed

        player: the player
        """
        if self.getPlayer(player.name):
            assert self.members[player.name] == player
            trace(Level.info, "Player={} rejoined the team".format(player.name))
            return

        self.members[player.name] = player
        self._updateMsgSrc()

    def getPlayer(self, playerName):
        """ Gets the player assocaited with that name.
            Return None if no such player found
        """
        return self.members.get(playerName, None)

    def ready(self):
        """ Returns true if team has enough ready players to start the game"""
        if len(self.members) < 2:
            trace(Level.info, "Team", self.teamNumber, "has",
                len(self.members), "(less than two) players")
            return False

        if all(plyr.ready for plyr in self.members.values()):
            return True
        trace(Level.info, "Team", self.teamNumber, "some players are not ready")
        return False
