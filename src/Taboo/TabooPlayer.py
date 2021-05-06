""" Taboo Player"""
from fwk.MsgSrc import Connections
from Taboo.TabooTeam import TabooTeam

class TabooPlayer:

    def __init__(self, txQueue, name, team, turnsPlayed=0):
        """ Creates a taboo player associated to a team. Self-registers to the team

        txQueue: tx queue
        name: player name
        team: team that this player should belong to
        """
        self.name = name
        self.playerConns = Connections(txQueue)
        team.addPlayer(self)
        self.team = team
        self.turnsPlayed = turnsPlayed
        self.__ready = False

    def __str__(self):
        return "TabooPlayer({}) teamId={}, turnsPlayed={}".format(self.name,
                self.team.teamNumber,
                self.turnsPlayed)

    def addConn(self, ws):
        self.playerConns.addConn(ws)
        self.team.conns.addConn(ws)

    def delConn(self, ws):
        self.playerConns.delConn(ws)
        self.team.conns.delConn(ws)

    @property
    def ready(self):
        return self.__ready

    @ready.setter
    def ready(self, flag):
        self.__ready = flag

    def numConns(self):
        return self.playerConns.count()
