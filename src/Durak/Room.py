"""Defines a durak room in bari"""

from enum import Enum
import random

from fwk.Exceptions import InvalidDataException
from fwk.GamePlugin import GamePlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)

from Common.Card import Card

from Durak.HostParametersMsgSrc import HostParametersMsgSrc
from Durak.Player import Player
from Durak.Round import Round

class GameState(Enum):
    WAITING_TO_START = 1
    RUNNING = 2
    GAME_OVER = 3

class Room(GamePlugin):
    """Defines a durak room"""
    def __init__(self, path, name, hostParameters, state=GameState.WAITING_TO_START):
        super(Room, self).__init__(path, name)
        self.hostParameters = hostParameters
        self.state = state

        self.playerByWs = {}   #<ws:player>
        self.playerByName = {} # name --> player

        self.playerTurnOrder = []
        self.round = None

        # Initialized after queues are set up
        self.hostParametersMsgSrc = None
        self.gameOverMsgSrc = None
        self.scoreMsgSrc = None

    def initGame(self):
        """Called one time after queues are instantiated"""
        self.hostParametersMsgSrc = HostParametersMsgSrc(self.conns, self.hostParameters)

    def processMsg(self, qmsg):
        if super(Room, self).processMsg(qmsg):
            return True

        if qmsg.jmsg[0] == "JOIN":
            return self.__processJoin(qmsg)

        if qmsg.jmsg[0] == "ATTACK":
            return self.__processAttack(qmsg)

        return True

    def postProcessConnect(self, ws):
        # Publish GAME-STATUS with number of clients connected to this room
        self.playerByWs[ws] = None
        self.publishGiStatus()

    def postProcessDisconnect(self, ws):
        # Publish GAME-STATUS with number of clients connected to this room
        player = self.playerByWs[ws]
        if player:
            player.delConn(ws)
        del self.playerByWs[ws]
        self.publishGiStatus()

    def postQueueSetup(self):
        """Invoked when the RX+TX queues are set up to the room and
        when the self.conns object is setup to track all clients in the room
        """
        self.initGame()
        self.publishGiStatus()

    def publishGiStatus(self):
        # Publish number of clients connected to this room
        self.txQueue.put_nowait(InternalGiStatus(
            [{"clients": self.conns.count()}], self.path))

    #--------------------------------------------
    # Join handling

    def __processJoin(self, qmsg):
        """
        ["JOIN", playerName]
        """
        ws = qmsg.initiatorWs

        if self.state == GameState.GAME_OVER:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD",
                                                 "Game over"],
                                                {ws}, initiatorWs=ws))
            return True

        assert ws in self.playerByWs, "Join request from an unrecognized connection"

        if self.playerByWs[ws]:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD",
                                                 "Unexpected JOIN from joined player"],
                                                {ws}, initiatorWs=ws))
            return True

        if len(qmsg.jmsg) != 2:
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        _, playerName = qmsg.jmsg

        if not isinstance(playerName, str):
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD", "Invalid player name", playerName],
                                                {ws}, initiatorWs=ws))
            return True

        return self.joinPlayer(ws, playerName)

    def joinPlayer(self, ws, playerName):
        player = self.playerByName.get(playerName)

        numPlayersBeforeJoin = len(self.playerByName)
        if not player:
            # New player
            if numPlayersBeforeJoin == self.hostParameters.numPlayers:
                # Can't accept new players
                self.txQueue.put_nowait(ClientTxMsg(
                    ["JOIN-BAD", "Enough players joined already/bad player name",
                     playerName],
                    {ws}, initiatorWs=ws))
                return True

            player = Player(self.txQueue, self.conns, playerName)
            self.playerByName[playerName] = player

        player.addConn(ws)
        self.playerByWs[ws] = player

        self.txQueue.put_nowait(ClientTxMsg(["JOIN-OKAY", player.name],
            {ws}, initiatorWs=ws))

        if (numPlayersBeforeJoin + 1 == self.hostParameters.numPlayers and
            len(self.playerByName) == self.hostParameters.numPlayers):
            # Enough players joined
            self.startGame()

        self.publishGiStatus()
        return True

    def startGame(self):
        if not self.round:
            # Starting first round
            self.state = GameState.RUNNING

            # - Setup player turn order
            self.playerTurnOrder = list(self.playerByName)
            random.shuffle(self.playerTurnOrder)


            # - Create round object
            self.round = Round(
                self.txQueue,
                self.conns,
                self.hostParameters,
                self.playerByName,
                self.playerTurnOrder,
            )

        self.round.startRound()

    #--------------------------------------------
    # Attack handling

    def __processAttack(self, qmsg):
        """
        ["ATTACK", [ attackCard1, attackCard2, ... ]]
        """
        ws = qmsg.initiatorWs

        if self.state != GameState.RUNNING:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD",
                                                 "Game not running"],
                                                {ws}, initiatorWs=ws))
            return True

        assert ws in self.playerByWs, "Attack request from an unrecognized connection"

        player = self.playerByWs[ws]

        if player is None:
            # Spectators are added as None to playerByWs
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD",
                                                 "Must join the game first"],
                                                {ws}, initiatorWs=ws))
            return True

        if len(qmsg.jmsg) != 2:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        _, attacks = qmsg.jmsg

        if not isinstance(attacks, list):
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Invalid attacks", attacks],
                                                {ws}, initiatorWs=ws))
            return True

        cards = []
        for cardJmsg in attacks:
            try:
                card = Card.fromJmsg(cardJmsg)
            except InvalidDataException as _:
                self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Invalid card", cardJmsg],
                                                    {ws}, initiatorWs=ws))
                return True

            cards.append(card)

        return self.round.playerAttack(ws, player, cards)
