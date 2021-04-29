"""Taboo room"""

from enum import Enum
import re

from fwk.GamePlugin import GamePlugin
from fwk.Trace import (
        trace,
        Level,
)
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)
from Taboo.HostParametersMsgSrc import HostParametersMsgSrc
from Taboo.TabooPlayer import TabooPlayer
from Taboo.TabooTeam import TabooTeam
from Taboo.TurnManager import TurnManager
from Taboo.WordSets import SupportedWordSets

validPlayerNameRe = re.compile("^[a-zA-Z0-9_]+$")

class GameState(Enum):
    WAITING_TO_START = 1
    RUNNING = 2
    GAME_OVER = 3

class TabooRoom(GamePlugin):
    def __init__(self, path, name, hostParameters, state=GameState.WAITING_TO_START):
        super(TabooRoom, self).__init__(path, name)
        self.hostParameters = hostParameters
        self.state = state

        self.playerByWs = {} #<ws:player>
        self.teams = None # int -> Team
        self.wordSet = SupportedWordSets[self.hostParameters.wordSets[0]]

        # Initialized after queues are set up
        self.hostParametersMsgSrc = None
        self.turnMgr = None

    def initGame(self):
        self.hostParametersMsgSrc = HostParametersMsgSrc(self.conns, self.hostParameters)
        self.teams = {n: TabooTeam(self.txQueue, n)
                      for n in range(1, self.hostParameters.numTeams + 1)}

        self.turnMgr = TurnManager(self.txQueue, self.wordSet,
                                   self.teams, self.hostParameters,
                                   self.conns)

    def publishGiStatus(self):
        """Invoked to update the lobby of the game instance (room) status

               ["GAME-STATUS", <path:str>, {"gameState": <str>,
                                            "clientCount": <str>,
                                            "spectatorCount": <int>,
                                            "hostParams": <dict>}]
        """
        jmsg = [{"hostParameters": self.hostParameters.toJmsg()[0],
                 "clientCount": self.conns.count()}]
        self.txQueue.put_nowait(InternalGiStatus(jmsg, self.path))

    def postQueueSetup(self):
        """Invoked when the RX+TX queues are set up to the room and
        when the self.conns object is setup to track all clients in the room
        """
        self.initGame()
        self.publishGiStatus()

    def postProcessConnect(self, ws):
        """Invoked when a new client (websocket) connects from the room.
        Note that no messages have been exchanged yet
        """
        self.playerByWs[ws] = None
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        """Invoked when a client disconnects from the room"""
        assert ws in self.playerByWs, "Invalid disconnect on a non-existant connection"
        player = self.playerByWs[ws]
        if player:
            player.delConn(ws)
        del self.playerByWs[ws]
        self.publishGiStatus()

    def processMsg(self, qmsg):
        """Handle messages from the queue coming to this room

            message-type1: ["JOIN", ...]
        """
        if super(TabooRoom, self).processMsg(qmsg):
            return True

        if qmsg.jmsg[0] == "JOIN":
            return self.__processJoin(qmsg)

        # When the last READY message is received, we should call
        # self.turnManager.startNewWord() which picks the
        # next player to play (but not necessarily the next word to
        # play). We should also switch self.state == GameState.RUNNING

        if qmsg.jmsg[0] == "KICKOFF":
            return self.__processKickoff(qmsg)

        return False

    def __processKickoff(self, qmsg):
        ws = qmsg.initiatorWs

        if len(qmsg.jmsg) != 1:
            self.txQueue.put_nowait(ClientTxMsg(["KICKOFF-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        if self.state != GameState.RUNNING:
            self.txQueue.put_nowait(ClientTxMsg(["KICKOFF-BAD",
                                                 "Game not running yet"],
                                                 {ws}, initiatorWs=ws))
            return True

        player = self.playerByWs[ws]
        if player != self.turnMgr.activePlayer:
            self.txQueue.put_nowait(ClientTxMsg(["KICKOFF-BAD",
                                                 "It is not your turn"],
                                                 {ws}, initiatorWs=ws))
            return True

        return self.turnMgr.processKickoff(qmsg)

    def __processJoin(self, qmsg):
        """
        ["JOIN", playerName, team:int={0..T}]
        """
        ws = qmsg.initiatorWs

        assert ws in self.playerByWs, "Join request from an unrecognized connection"

        if self.playerByWs[ws]:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD",
                                                 "Unexpected JOIN message from client that "
                                                 "has already joined"], {ws}, initiatorWs=ws))
            return True

        if len(qmsg.jmsg) != 3:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        _, playerName, teamNumber = qmsg.jmsg

        if not isinstance(playerName, str) or not validPlayerNameRe.match(playerName):
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid player name", playerName],
                                                {ws}, initiatorWs=ws))
            return True

        if (not isinstance(teamNumber, int) or
            teamNumber < 0 or teamNumber >= self.hostParameters.numTeams):
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid team number", teamNumber],
                                                {ws}, initiatorWs=ws))
            return True

        return self.joinPlayer(ws, playerName, teamNumber)


    def joinPlayer(self, ws, playerName, teamNumber):
        player = self.getPlayer(playerName)

        # A new player joins
        if not player:
            team = self.__getTeam(teamNumber)
            player = TabooPlayer(self.txQueue, playerName, team)
            self.__finalizeJoin(ws, player)
            #self.processEvent(PlayerJoin(player))
            return True

        #new join-request for an existing player will be accepted
        #but we ignore the requested team and associate the player to the original team
        if teamNumber != team.teamNumber:
            trace(Level.warn, "Player {} forced to join their "
                "original team {}".format(player.name, team.teamNumber))

        self.__finalizeJoin(ws, player)
        return True

    def getPlayer(self, playerName):
        """ Returns player

            player: player matching the name
                None if no player exists by that name
        """
        for t in self.teams.values():
            v = t.getPlayer(playerName)
            if v is not None:
                return v
        return None

    def __finalizeJoin(self, ws, player):
        player.addConn(ws)
        self.playerByWs[ws] = player
        self.txQueue.put_nowait(ClientTxMsg(["JOIN-OKAY", player.name, player.team.teamNumber],
            {ws}, initiatorWs=ws))

    def spectatorCount(self):
        return sum(1 for plyr in self.playerByWs.values() if not plyr)

    def __getTeam(self, teamNumber):
        team = self.teams.get(teamNumber)
        if not team:
            return min(self.teams.values(), key=lambda t: len(t.members))
        return team
