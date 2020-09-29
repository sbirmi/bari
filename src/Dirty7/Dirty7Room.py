"""Dirty7 game instance"""

import re

from fwk.GamePlugin import GamePlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)
from Dirty7.Dirty7Game import (
        GameState,
        Player,
)

validPlayerNameRe = re.compile("^[a-zA-Z0-9_]+$")
validPasswdRe = re.compile("^[a-zA-Z0-9_]+$")

PLAYER_JOINED = 1
START_ROUND = 2
ADVANCE_TURN = 3
STOP_ROUND = 4
STOP_GAME = 5

class Dirty7Room(GamePlugin):
    def __init__(self, path, name, hostParameters):
        GamePlugin.__init__(self, path, name)
        self.hostParameters = hostParameters

        self.gameState = GameState.WAITING_FOR_PLAYERS
        self.playerByName = {}
        self.playerByWs = {}

    def processEvent(self, event):
        if event == PLAYER_JOINED:
            # A new player has joined
            assert self.gameState == GameState.WAITING_FOR_PLAYERS
            if len(self.playerByName) == self.hostParameters.numPlayers:
                self.processEvent(START_ROUND)
                return

            # Wait for more players
            self.publishGiStatus()

        elif event == START_ROUND:
            self.gameState = GameState.ROUND_START

            self.publishGiStatus()

        elif event == ADVANCE_TURN:
            pass

        elif event == STOP_ROUND:
            pass

        elif event == STOP_GAME:
            pass

        else:
            assert False

    def processJoin(self, qmsg): # pylint: disable=too-many-return-statements
        """
        ["JOIN", playerName, passwd, (avatar)]
        """
        ws = qmsg.initiatorWs

        if ws not in self.playerByWs or self.playerByWs[ws]:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD",
                                                 "Unexpected JOIN message from client that "
                                                 "has already joined"], {ws}, initiatorWs=ws))
            return True


        if len(qmsg.jmsg) != 3:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        _, playerName, passwd = qmsg.jmsg

        if not isinstance(playerName, str) or not validPlayerNameRe.match(playerName):
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid player name", playerName],
                                                {ws}, initiatorWs=ws))
            return True

        if not isinstance(passwd, str) or not validPasswdRe.match(passwd):
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid password", passwd],
                                                {ws}, initiatorWs=ws))
            return True

        if (playerName not in self.playerByName and
                len(self.playerByName) < self.hostParameters.numPlayers):
            # Add a new player
            player = Player(self.txQueue, playerName, passwd)
            player.playerConns.addConn(ws)
            self.playerByWs[ws] = player
            self.playerByName[playerName] = player
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-OKAY"], {ws}, initiatorWs=ws))

            self.processEvent(PLAYER_JOINED)
            return True

        if playerName not in self.playerByName and self.gameState != GameState.WAITING_FOR_PLAYERS:
            # New player trying to join after the game has started
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid player name/password or "
                                                 "trying to join a running game"],
                                                {ws}, initiatorWs=ws))
            return True

        if playerName in self.playerByName and passwd != self.playerByName[playerName].passwd:
            # Bad password
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Bad password"],
                                                {ws}, initiatorWs=ws))
            return True

        assert playerName in self.playerByName
        assert passwd == self.playerByName[playerName].passwd
        self.txQueue.put_nowait(ClientTxMsg(["JOIN-OKAY"], {ws}, initiatorWs=ws))

        # Move ws to player
        player = self.playerByName[playerName]
        player.playerConns.addConn(ws)
        self.playerByWs[ws] = player

        return True

    def processMsg(self, qmsg):
        if super(Dirty7Room, self).processMsg(qmsg):
            return True

        if qmsg.jmsg[0] == "JOIN":
            return self.processJoin(qmsg)
        return False

    def postQueueSetup(self):
        pass

    def postProcessConnect(self, ws):
        # ws connected but not joined as a player yet
        self.playerByWs[ws] = None
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        if self.playerByWs.get(ws, None):
            try:
                self.playerByWs[ws].playerConns.delConn(ws)
            except KeyError:
                pass

        try:
            del self.playerByWs[ws]
        except KeyError:
            pass

        self.publishGiStatus()


    def publishGiStatus(self):
        # Publish number of clients connected to this room
        self.txQueue.put_nowait(InternalGiStatus(
            [{"gameState": self.gameState}] + self.hostParameters.toJmsg(), self.path))
