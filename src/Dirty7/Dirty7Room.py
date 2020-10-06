"""Dirty7 game instance"""

import random
import re

from fwk.GamePlugin import GamePlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)
from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)
from fwk.Trace import (
        Level,
        trace,
)
from Dirty7.Card import (
        Card,
)
from Dirty7.Dirty7Game import (
        StateGameBegin,
        StateGameOver,
        StatePlayerTurn,
        StateRoundStart,
        StateRoundStop,
        StateWaitingForPlayers,
        Player,
)
from Dirty7.Dirty7Round import (
        Round,
        Turn,
)
from Dirty7.Exceptions import (
        InvalidDataException,
        InvalidPlayException,
)
from Dirty7.Events import (
        AdvanceTurn,
        Declare,
        GameBegin,
        GameOver,
        PlayerJoin,
        StartRound,
        StopRound,
)

validPlayerNameRe = re.compile("^[a-zA-Z0-9_]+$")
validPasswdRe = re.compile("^[a-zA-Z0-9_]+$")

class Dirty7Room(GamePlugin):
    """
    When a websocket has connected but hasn't joined:
        playerByWs[ws] == None
    As soon as the websocket sends a vailid JOIN message,
        playerByWs[ws] == Player(..)
    """
    def __init__(self, path, name, hostParameters):
        GamePlugin.__init__(self, path, name)
        self.hostParameters = hostParameters

        self.gameState = StateWaitingForPlayers()
        self.playerByName = {}
        self.playerByWs = {}
        self.rounds = []
        self.currRoundTurn = None

        self.winners = None

    @property
    def currRound(self):
        return self.rounds[-1]

    def newRound(self, startRound):
        roundNum = startRound.roundNum
        trace(Level.rnd, self.path, "starting round", roundNum)

        self.currRoundTurn = Turn(self.conns, roundNum, startRound.turnOrderNames,
                                  startRound.turnIdx)

        # Get round parameters
        roundParameters = self.hostParameters.roundParameters(roundNum)

        round_ = Round(self.path, self.conns, roundParameters,
                       self.playerByName, self.currRoundTurn)
        self.rounds.append(round_)

    def startGame(self):
        trace(Level.game, self.path, "starting")

    def totalScore(self):
        totalScoreByName = {name: 0 for name in self.playerByName}
        for round_ in self.rounds:
            scoreByName = round_.roundScore.scoreByPlayerName
            for name, score in (scoreByName or {}).items():
                if score:
                    totalScoreByName[name] += score
        return totalScoreByName

    def processEvent(self, event):
        trace(Level.game, "processEvent", str(event), "in state", self.gameState)
        if isinstance(event, PlayerJoin):
            # A new player has joined
            assert isinstance(self.gameState, StateWaitingForPlayers)

            if len(self.playerByName) == self.hostParameters.numPlayers:
                self.processEvent(GameBegin())
                return

            # Waiting for more players
            self.publishGiStatus()
            return

        if isinstance(event, GameBegin):
            assert isinstance(self.gameState, StateWaitingForPlayers)
            self.startGame()
            self.gameState = StateGameBegin()
            turnOrderNames = list(self.playerByName)
            random.shuffle(turnOrderNames)
            self.processEvent(StartRound(1, turnOrderNames, 0))
            return

        if isinstance(event, StartRound):
            assert isinstance(self.gameState, (StateGameBegin, StateRoundStop))
            self.gameState = StateRoundStart()
            self.newRound(event)
            self.gameState = StatePlayerTurn()
            self.publishGiStatus()
            return

        if isinstance(event, AdvanceTurn):
            self.currRound.turn.advance(event)
            return

        if isinstance(event, StopRound):
            assert isinstance(self.gameState, StatePlayerTurn)
            self.gameState = StateRoundStop()

            # Stop the current round (mark it as round-over) so that
            # irrelevant notifications are not sent out
            self.currRound.makeRoundOver()

            # Check if the end of game limit is hit. Trigger
            # GameOver in which case
            totalScore = self.totalScore()
            maxScore = max(totalScore.values())
            if maxScore >= self.hostParameters.stopPoints:
                self.processEvent(GameOver())
                return

            # Else, start a new round
            self.processEvent(StartRound(self.currRound.roundNum+1,
                                         self.currRound.turn.playerNameInTurnOrder,
                                         turnIdx=(self.currRound.turn.turnIdx + 1) %
                                         self.hostParameters.numPlayers))
            return

        if isinstance(event, GameOver):
            assert isinstance(self.gameState, StateRoundStop)
            self.gameState = StateGameOver()
            self.publishGiStatus()

            totalScore = self.totalScore()
            lowestScore = min(totalScore.values())

            winners = [name for name, score in totalScore.items() if score == lowestScore]
            jmsg = ["GAME-OVER", winners]

            self.winners.setMsgs([Jmai(jmsg, initiatorWs=None)])
            return

        if isinstance(event, Declare):
            assert isinstance(self.gameState, StatePlayerTurn)
            self.currRound.declare(event) # calculate points based on declaring
            self.processEvent(StopRound(self.currRound.roundParams.roundNum))
            return

        trace(Level.error, "Invalid event received", str(event))
        assert False

    def processJoin(self, qmsg):
        """
        ["JOIN", playerName, passwd, (avatar)]
        """
        ws = qmsg.initiatorWs

        if isinstance(self.gameState, StateGameOver):
            self.txQueue.put_nowait(ClientTxMsg(["JOIN-BAD",
                                                 "Game over already"], {ws}, initiatorWs=ws))
            return True

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

            self.processEvent(PlayerJoin(player))
            return True

        if playerName not in self.playerByName and not isinstance(self.gameState,
                                                                  StateWaitingForPlayers):
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

    def processPlay(self, qmsg):
        """
        ["PLAY", {"dropCards": list of cards,
                  "numDrawCards": int,
                  "pickCards": list of cards}]
        Should only be processed if:
        1. game state is player turn
        2. ws has joined
        3. player[ws].name == turn.current()
        """
        ws = qmsg.initiatorWs

        if not isinstance(self.gameState, StatePlayerTurn):
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Can't make moves now"],
                                                {ws}, initiatorWs=ws))
            return True

        if self.playerByWs[ws] is None:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "You must join the game first"],
                                                {ws}, initiatorWs=ws))
            return True

        if self.playerByWs[ws].name != self.currRound.turn.current():
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "It is not your turn"],
                                                {ws}, initiatorWs=ws))
            return True

        if len(qmsg.jmsg) != 2:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        playDesc = qmsg.jmsg[1]
        if not isinstance(playDesc, dict):
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Invalid move description"],
                                                {ws}, initiatorWs=ws))
            return True
        playDesc = dict(playDesc)

        # dropCards
        dropCards = playDesc.pop("dropCards", [])
        if not isinstance(dropCards, list):
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Invalid cards being dropped",
                                                 dropCards], {ws}, initiatorWs=ws))
            return True

        try:
            dropCards = [Card.fromJmsg(cd) for cd in dropCards]
        except InvalidDataException as exc:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD"] + exc.toJmsg(),
                                                {ws}, initiatorWs=ws))
            return True

        # numDrawCards
        numDrawCards = playDesc.pop("numDrawCards", 0)
        if not isinstance(numDrawCards, int):
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Drawing invalid number of cards",
                                                 numDrawCards], {ws}, initiatorWs=ws))
            return True

        # pickCards
        pickCards = playDesc.pop("pickCards", [])
        if not isinstance(pickCards, list):
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Invalid cards being drawn",
                                                 pickCards], {ws}, initiatorWs=ws))
            return True

        try:
            pickCards = [Card.fromJmsg(cd) for cd in pickCards]
        except InvalidDataException as exc:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD"] + exc.toJmsg(),
                                                {ws}, initiatorWs=ws))
            return True

        # If item remain in play-description, complain
        if playDesc:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Unrecognized play description",
                                                 playDesc], {ws}, initiatorWs=ws))
            return True

        # If the deck doesn't have numDrawCards
        if self.currRound.tableCards.deckCardCount() < numDrawCards:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Drawing invalid number of cards",
                                                 numDrawCards], {ws}, initiatorWs=ws))
            return None

        # pickCards should be in revealedCards
        if not self.currRound.tableCards.revealedCardsContains(pickCards):
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Picking cards not available",
                                                 [cd.toJmsg() for cd in pickCards]], {ws},
                                                initiatorWs=ws))
            return True

        event = self.currRound.rule.processPlay(self.currRound, self.playerByWs[ws],
                                                dropCards, numDrawCards, pickCards)

        if not event:
            self.txQueue.put_nowait(ClientTxMsg(["PLAY-BAD", "Invalid play"],
                                                {ws}, initiatorWs=ws))
        else:
            jmsg = ["UPDATE", self.currRound.roundParams.roundNum,
                    {"PLAY": [self.playerByWs[ws].name,
                              [cd.toJmsg() for cd in dropCards],
                              numDrawCards,
                              [cd.toJmsg() for cd in pickCards]] +
                             event.toJmsg()}]
            self.broadcast(jmsg)
            self.processEvent(event)

        return True

    def processDeclare(self, qmsg):
        """
        ["DECLARE"]
        Should only be processed if:
        1. game state is player turn
        2. ws has joined
        3. player[ws].name == turn.current()
        """
        ws = qmsg.initiatorWs

        if not isinstance(self.gameState, StatePlayerTurn):
            self.txQueue.put_nowait(ClientTxMsg(["DECLARE-BAD", "Can't make moves now"],
                                                {ws}, initiatorWs=ws))
            return True

        if self.playerByWs[ws] is None:
            self.txQueue.put_nowait(ClientTxMsg(["DECLARE-BAD", "You must join the game first"],
                                                {ws}, initiatorWs=ws))
            return True

        if self.playerByWs[ws].name != self.currRound.turn.current():
            self.txQueue.put_nowait(ClientTxMsg(["DECLARE-BAD", "It is not your turn"],
                                                {ws}, initiatorWs=ws))
            return True

        if len(qmsg.jmsg) != 1:
            self.txQueue.put_nowait(ClientTxMsg(["DECLARE-BAD", "Invalid message length"],
                                                {ws}, initiatorWs=ws))
            return True

        event = self.currRound.rule.processDeclare(self.currRound, self.playerByWs[ws])

        if not event:
            self.txQueue.put_nowait(ClientTxMsg(["DECLARE-BAD", "Invalid declare"],
                                                {ws}, initiatorWs=ws))
        else:
            jmsg = ["UPDATE", self.currRound.roundParams.roundNum,
                    {"DECLARE": event.toJmsg()}]
            self.broadcast(jmsg)
            self.processEvent(event)

        return True

    def processMsg(self, qmsg):
        if super(Dirty7Room, self).processMsg(qmsg):
            return True

        if qmsg.jmsg[0] == "JOIN":
            return self.processJoin(qmsg)

        if qmsg.jmsg[0] == "PLAY":
            return self.processPlay(qmsg)

        if qmsg.jmsg[0] == "DECLARE":
            return self.processDeclare(qmsg)

        return False

    def postQueueSetup(self):
        self.publishGiStatus()
        self.winners = MsgSrc(self.conns)

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

    def spectatorCount(self):
        return sum(1 for plyr in self.playerByWs.values() if not plyr)

    def publishGiStatus(self):
        # Publish number of clients connected to this room
        jmsg = [{"gameState": self.gameState.toJmsg(),
                 "clientCount": {name: player.playerConns.count() for name, player in
                                 self.playerByName.items()},
                 "spectatorCount": self.spectatorCount()}]
        jmsg += self.hostParameters.toJmsg()
        if self.rounds:
            jmsg += self.currRound.roundParams.toJmsg()
        self.txQueue.put_nowait(InternalGiStatus(jmsg, self.path))
