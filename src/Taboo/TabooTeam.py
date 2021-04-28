""" Taboo Team"""

from fwk.Trace import (
    trace,
    Level,
)

class TabooTeam:
    """ Creates a team with a specified teamNumber

    """
    def __init__(self, teamNumber):
        self.teamNumber = teamNumber
        self.members = {}

    def addPlayer(self, player):
        """ Players need to be unique. Reset not allowed

        player: the player
        """
        if self.getPlayer(player.name):
            assert self.members[player.name] == player
            trace(Level.info, "Player={} rejoined the team".format(player.name))
            return

        self.members[player.name] = player

    def getPlayer(self, playerName):
        """ Gets the player assocaited with that name.
            Return None if no such player found
        """
        return self.members.get(playerName, None)
