"""Taboo room"""
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

validPlayerNameRe = re.compile("^[a-zA-Z0-9_]+$")

class TabooRoom(GamePlugin):
    def __init__(self, path, name, hostParameters):
        super(TabooRoom, self).__init__(path, name)
        self.hostParameters = hostParameters
        self.hostParametersMsgSrc = None
        self.playerByWs = {} #<ws:player>
        self.teams = {} #<teamNumber:team>

    def init_game(self):
        self.hostParametersMsgSrc = HostParametersMsgSrc(self.conns, self.hostParameters)

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
        self.init_game()
        self.publishGiStatus()

    def postProcessConnect(self, ws):
        """Invoked when a new client (websocket) connects from the room.
        Note that no messages have been exchanged yet
        """
        self.playerByWs[ws] = None
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        """Invoked when a client disconnects from the room"""
        if self.playerByWs.get(ws, None):
            try:
                self.playerByWs[ws].delConn(ws)
            except KeyError:
                pass

        try:
            del self.playerByWs[ws]
        except KeyError:
            pass

        self.publishGiStatus()

    def processMsg(self, qmsg):
        """Handle messages from the queue coming to this room

            message-type1: ["JOIN", ...]
        """
        if super(TabooRoom, self).processMsg(qmsg):
            return True

        if qmsg.jmsg[0] == "JOIN":
            return self.__processJoin(qmsg)

        return False

    def __processJoin(self, qmsg):
        """
        ["JOIN", playerName, team:int={0..T}]
        """
        ws = qmsg.initiatorWs

        if ws not in self.playerByWs or self.playerByWs[ws]: #QQ
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

        player, team = self.getPlayer(playerName)

        # A new player joins
        if not player:
            if teamNumber not in self.teams:
                #A new team
                self.teams[teamNumber] = TabooTeam(teamNumber)
            team = self.teams.get(teamNumber)
            player = TabooPlayer(self.txQueue, playerName, team)
            self.__finalize_join(ws, player, team.teamNumber)
            #self.processEvent(PlayerJoin(player))
            return True

        assert team is not None, "What happened!"
        #new join-request for an existing player will be accepted
        #but we ignore the requested team and associate the player to the original team
        if teamNumber != team.teamNumber:
            trace(Level.warn, "Player {} forced to join their "
            "original team {}".format(player.name, team.teamNumber))

        self.__finalize_join(ws, player, team.teamNumber)
        return True

    def getPlayer(self, playerName):
        """ Returns (player, team)

            player: player matching the name
            team: team it belongs to

            (None, None) if no player exists by that name
        """
        for t in self.teams.values():
            v = t.getPlayer(playerName)
            if v is not None:
                return (v, t)
        return (None, None)

    def __finalize_join(self, ws, player, teamNumber):
        player.addConn(ws)
        self.playerByWs[ws] = player
        self.txQueue.put_nowait(ClientTxMsg(["JOIN-OKAY", player.name, teamNumber],
            {ws}, initiatorWs=ws))

    def spectatorCount(self):
        return sum(1 for plyr in self.playerByWs.values() if not plyr)
