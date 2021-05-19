""" Taboo Player"""
from fwk.MsgSrc import (
        Connections,
        Jmai,
        MsgSrc,
)
from Taboo.TabooTeam import TabooTeam

class TabooPlayer:

    def __init__(self, txQueue, allConns, name, team, turnsPlayed=0):
        """ Creates a taboo player associated to a team. Self-registers to the team

        txQueue: tx queue
        allConns: Connections with all clients in the room
        name: player name
        team: team that this player should belong to
        """
        self.name = name
        self.team = team
        self.turnsPlayed = turnsPlayed

        self.__ready = False
        self.playerConns = Connections(txQueue)
        team.addPlayer(self)

        self.playerStatusMsgSrc = MsgSrc(allConns)

    def __str__(self):
        return "TabooPlayer({}) teamId={}, turnsPlayed={}".format(self.name,
                self.team.teamNumber,
                self.turnsPlayed)

    def addConn(self, ws):
        self.playerConns.addConn(ws)
        self.team.conns.addConn(ws)
        self._updateMsgSrc()

    def delConn(self, ws):
        self.playerConns.delConn(ws)
        self.team.conns.delConn(ws)
        self._updateMsgSrc()

    @property
    def ready(self):
        return self.__ready

    @ready.setter
    def ready(self, flag):
        self.__ready = flag
        self._updateMsgSrc()

    def incTurnsPlayed(self):
        self.turnsPlayed += 1

    def numConns(self):
        return self.playerConns.count()

    def _updateMsgSrc(self):
        self.playerStatusMsgSrc.setMsgs([
            Jmai(["PLAYER-STATUS", self.name,
                  {"numConns": self.numConns(),
                   "ready": self.ready,
                   "turnsPlayed": self.turnsPlayed,
            }], None),
        ])
