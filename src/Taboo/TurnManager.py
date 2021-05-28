"""Turn manager. Starts new turns etc"""

from collections import defaultdict
import datetime
from enum import Enum
import random

from fwk.Msg import (
        ClientTxMsg,
        TimerRequest,
)
from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)
from fwk.Trace import (
        trace,
        Level,
)
from Taboo.ScoreMsgSrc import ScoreMsgSrc
from Taboo.Word import (
        Word,
        WordState,
)

def expiryEpoch(turnDurationSec):
    utcnow = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    return utcnow + turnDurationSec

class TurnMgrState(Enum):
    GAME_START_WAIT = 0
    KICKOFF_WAIT = 1
    RUNNING = 2
    GAME_OVER = 3

class TurnManager:
    def __init__(self, path, txQueue, wordSet, teams, hostParameters, allConns,
                 gameOverCb):
        """
        Arguments
        ---------
        gameOverCb : asyncio.Queue
        wordSet : WordSet
        teams : dict[int: TabooTeam]
        hostParameters : HostParameters
        allConns : Connections
        gameOverCb : function (no args)
            Normally, the return value from TurnManager can signal to the game room
            if the game gets over. However, when the timer expires (timer handler
            is invoked from the Bari core), we need a way to call just the gameOver
            function in the Room. An ugly way is to pass the whole room here which
            I am avoiding by passing in gameOverCb instead.
        """
        self._path = path
        self._txQueue = txQueue
        self._wordSet = wordSet
        self._teams = teams
        self._hostParameters = hostParameters # Stop the game when every live player
                                              # has played hostParameters.numTurns
        self._allConns = allConns
        self._gameOverCb = gameOverCb

        self._wordsByTurnId = defaultdict(list)

        self._curTurnId = 0
        self._curTurn = None # Points to the current turn in play
        self._activePlayer = None
        self._waitForKickoffMsgSrc = MsgSrc(self._allConns)
        self._utcTimeout = None # UTC epoch of when this turn expires

        self._state = TurnMgrState.GAME_START_WAIT

        self._scoreMsgSrc = ScoreMsgSrc(self._allConns, self._wordsByTurnId,
                                        set(self._teams))

    @property
    def activePlayer(self):
        return self._activePlayer

    @property
    def numTurns(self):
        return self._hostParameters.numTurns

    @property
    def turnDurationSec(self):
        return self._hostParameters.turnDurationSec

    @property
    def totalScore(self):
        return self._scoreMsgSrc.score

    def updateState(self, newState):
        if self._state == newState:
            return

        self._state = newState

        if newState == TurnMgrState.KICKOFF_WAIT:
            self._waitForKickoffMsgSrc.setMsgs([
                Jmai(["WAIT-FOR-KICKOFF", self._curTurnId, self._activePlayer.name], None),
            ])
        else:
            self._waitForKickoffMsgSrc.setMsgs([])

    # ---------------------------------
    # Message handlers

    def __validateCompletedOrDiscard(self, qmsg):
        """ Validates [COMPLETED|DISCARD, turn<int>, wordIdx<int>]
        Replies a DISCARD-BAD or COMPLETED-BAD if the message is
        received at wrong turn state

        Returns True iff message is valid
        """
        msgType = qmsg.jmsg[0]
        assert msgType in ("DISCARD", "COMPLETED")
        badReplyType = "{}-BAD".format(msgType)

        ws = qmsg.initiatorWs

        if self._state != TurnMgrState.RUNNING:
            trace(Level.play, "process{} turn state".format(msgType), self._state.name)
            self._txQueue.put_nowait(ClientTxMsg([badReplyType,
                                                  "Can't {} right now".format(msgType)],
                                                 {ws}, initiatorWs=ws))
            return False

        if qmsg.jmsg[1] != self._curTurnId:
            self._txQueue.put_nowait(ClientTxMsg([badReplyType,
                                                  "Invalid turn"],
                                                 {ws}, initiatorWs=ws))
            return False

        assert self._curTurnId in self._wordsByTurnId, (
                "Since the turn is in running state, {} must exist in {}".format(
                    self._curTurnId,
                    self._wordsByTurnId.keys()))

        assert self._wordsByTurnId[self._curTurnId], (
                "Since the turn is in running state, there must be at least 1 word in {}".format(
                    self._wordsByTurnId[self._curTurnId]))

        lastWord = self._wordsByTurnId[self._curTurnId][-1]

        if qmsg.jmsg[2] != lastWord.wordId:
            self._txQueue.put_nowait(ClientTxMsg([badReplyType,
                                                  "Invalid word"],
                                                 {ws}, initiatorWs=ws))
            return False

        if lastWord.state != WordState.IN_PLAY:
            self._txQueue.put_nowait(ClientTxMsg([badReplyType,
                                                  "The word is no longer in play"],
                                                 {ws}, initiatorWs=ws))
            return False

        return True

    def processCompletedOrDiscard(self, qmsg):
        """
        Guarantees from the caller
        1. qmsg.jmsg is of right length and right type
        2. Correct player is invoking this
        3. Game is not over yet

        Always returns True (message is ingested)
        """
        if not self.__validateCompletedOrDiscard(qmsg):
            return True

        lastWord = self._wordsByTurnId[self._curTurnId][-1]
        wordState = (WordState.COMPLETED if qmsg.jmsg[0] == "COMPLETED"
                        else WordState.DISCARDED)
        lastWord.resolve(wordState)
        self._scoreMsgSrc.updateTotal()

        if not self.startNextWord():
            # game over
            trace(Level.play, "Last word discarded/completed, no more words. Game over")
            self.activePlayer.incTurnsPlayed()
            self._gameOverCb()

        return True

    def processKickoff(self, qmsg):
        """Always returns True (implies message ingested)"""
        ws = qmsg.initiatorWs

        if self._state != TurnMgrState.KICKOFF_WAIT:
            self._txQueue.put_nowait(ClientTxMsg(["KICKOFF-BAD",
                                                  "Can't kickoff a turn"],
                                                  {ws}, initiatorWs=ws))
            return True

        # Start with a new word for the activePlayer

        ctx = {"turnId": self._curTurnId}
        self._txQueue.put_nowait(TimerRequest(self.turnDurationSec, self.timerExpiredCb, ctx))
        self._utcTimeout = expiryEpoch(self.turnDurationSec)

        assert self.startNextWord() is True, "Must always be able to start a new word"
        return True

    # ---------------------------------
    # Turn and word management

    def timerExpiredCb(self, ctx):
        """This method is invoked when the timer fires"""
        trace(Level.rnd, "Timer fired", ctx)

        if self._state == TurnMgrState.GAME_OVER:
            trace(Level.info, "Timer fired but game is already over. Nothing to do")
            return

        assert isinstance(ctx, dict)
        assert "turnId" in ctx

        if self._curTurnId != ctx["turnId"]:
            trace(Level.warn, "Timer fired for turn", ctx["turnId"],
                  "but turnMgr is on turn", self._curTurnId)
            return

        assert self._state == TurnMgrState.RUNNING, \
               "Turn must be running when the timer fires"

        lastWord = self._wordsByTurnId[self._curTurnId][-1]

        if lastWord.state != WordState.IN_PLAY:
            trace(Level.error, "The last word should be in play. This is unexpected")
            return

        self.activePlayer.incTurnsPlayed()

        lastWord.resolve(WordState.TIMED_OUT)
        self._scoreMsgSrc.updateTotal()

        turnStarted = self.startNewTurn()
        if not turnStarted:
            # Game over
            trace(Level.play, "Couldn't start a new turn. Game over")
            self.updateState(TurnMgrState.GAME_OVER)
            self._gameOverCb()

    def _findNextPlayer(self):
        """
        Returns TabooPlayer or None
        If a player should play next, return TabooPlayer else return None
        """
        candidatePlayersByTeam = {}
        for team in self._teams.values():
            candidatePlayers = [plyr for plyr in team.members.values()
                                if plyr.playerConns.count() > 0]
            if candidatePlayers:
                candidatePlayersByTeam[team.teamNumber] = \
                        sorted(candidatePlayers, key=lambda plyr: plyr.turnsPlayed)

        if not candidatePlayersByTeam:
            trace(Level.info, "no live players")
            return None

        if not any(any(True for plyr in plyrs if plyr.turnsPlayed < self.numTurns)
               for plyrs in candidatePlayersByTeam.values()):
            trace(Level.info, "All players have played atleast", self.numTurns, "turns")
            return None


        # Identify current team that's playing
        if self._wordsByTurnId:
            currentTeam = self._wordsByTurnId[self._curTurnId][-1].player.team
        else:
            currentTeam = random.choice(list(self._teams.values()))

        # Identify nextPlayer (preferring a player from the next team)
        teamCount = len(self._teams)
        for teamIdx in [1 + ((ti + currentTeam.teamNumber) % teamCount)
                        for ti in range(teamCount)]:
            if teamIdx not in candidatePlayersByTeam:
                # No live clients in this team
                continue

            nextPlayer = candidatePlayersByTeam[teamIdx][0]
            trace(Level.rnd, "next player", nextPlayer.name)
            return nextPlayer

        assert False, "Can't find a candidate in " + str(candidatePlayersByTeam)
        return None

    def startNewTurn(self):
        """
        Returns bool : true if new turn was started; false if the game is over
        """
        # 1. Find next player to go. If none is found, declare end of game
        self._activePlayer = self._findNextPlayer()
        if not self._activePlayer:
            trace(Level.rnd, "Can't start a new turn as no next player available")
            self.updateState(TurnMgrState.GAME_OVER)
            return False

        # 2. Start a new turn
        self._curTurnId += 1
        self._curTurn = None # No word selected to start

        if not self._wordSet.areWordsAvailable(self._path):
            trace(Level.rnd, "Words exhausted")
            self.updateState(TurnMgrState.GAME_OVER)
            return False

        self.updateState(TurnMgrState.KICKOFF_WAIT)
        return True

    def startNextWord(self):
        """
        Returns bool : True if new word started; false if the game is over
                       (no more words available)
        """
        assert self.activePlayer
        self.updateState(TurnMgrState.RUNNING)

        if self._wordsByTurnId[self._curTurnId]:
            trace(Level.debug,
                  "curTurnId", self._curTurnId,
                  "lastWord", self._wordsByTurnId[self._curTurnId][-1],
                  "state", self._wordsByTurnId[self._curTurnId][-1].state)
            assert self._wordsByTurnId[self._curTurnId][-1].state != WordState.IN_PLAY

        nextWordId = len(self._wordsByTurnId[self._curTurnId]) + 1

        # Fetch a new word
        found = self._wordSet.nextWord(self._path)
        if not found:
            trace(Level.rnd, "Can't start a new turn as no word available")
            # Ran out of words
            return False
        secret = found.word
        disallowed = found.disallowed
        trace(Level.rnd, "player", self.activePlayer.name, "word", secret)

        # Create a new Word
        turn = Word(self._curTurnId, nextWordId, secret, disallowed,
                    self.activePlayer, [team for team in self._teams.values()
                                   if team != self.activePlayer.team],
                    self._allConns,
                    self._utcTimeout)
        self._wordsByTurnId[self._curTurnId].append(turn)

        self._curTurn = turn
        return True
