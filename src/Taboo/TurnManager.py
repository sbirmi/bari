"""Turn manager. Starts new turns etc"""

from collections import defaultdict
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
from Taboo.Word import (
        Word,
        WordState,
)

class TurnMgrState(Enum):
    GAME_START_WAIT = 0
    KICKOFF_WAIT = 1
    RUNNING = 2
    GAME_OVER = 3

class TurnManager:
    def __init__(self, txQueue, wordSet, teams, hostParameters, allConns):
        self._txQueue = txQueue
        self._wordSet = wordSet
        self._teams = teams
        self._hostParameters = hostParameters # Stop the game when every live player
                                              # has played hostParameters.numTurns
        self._allConns = allConns

        self._wordsByTurnId = defaultdict(list)

        self._curTurnId = 0
        self._curTurn = None # Points to the current turn in play
        self._activePlayer = None
        self._waitForKickoffMsgSrc = MsgSrc(self._allConns)

        self._state = TurnMgrState.GAME_START_WAIT
        self._usedWordIdxs = set() # index of words used from self._wordSet

    @property
    def activePlayer(self):
        return self._activePlayer

    @property
    def numTurns(self):
        return self._hostParameters.numTurns

    @property
    def turnDurationSec(self):
        return self._hostParameters.turnDurationSec

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

    def processDiscard(self, qmsg):
        """
        Guarantees from the caller
        1. qmsg.jmsg is of right length and right type
        2. Correct player is invoking this
        3. Game is not over yet

        returns True if game over, else False
        """
        ws = qmsg.initiatorWs

        if self._state != TurnMgrState.RUNNING:
            trace(Level.play, "processDiscard turn state", self._state.name)
            self._txQueue.put_nowait(ClientTxMsg(["DISCARD-BAD",
                                                  "Can't discard right now"],
                                                 {ws}, initiatorWs=ws))
            return False

        if qmsg.jmsg[1] != self._curTurnId:
            self._txQueue.put_nowait(ClientTxMsg(["DISCARD-BAD",
                                                  "Discarding invalid turn"],
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
            self._txQueue.put_nowait(ClientTxMsg(["DISCARD-BAD",
                                                  "Discarding invalid word"],
                                                 {ws}, initiatorWs=ws))
            return False

        if lastWord.state != WordState.IN_PLAY:
            self._txQueue.put_nowait(ClientTxMsg(["DISCARD-BAD",
                                                  "The word is no longer in play"],
                                                 {ws}, initiatorWs=ws))
            return False

        lastWord.doDiscard()
        if not self.startNextWord():
            # game over
            trace(Level.play, "Last word discarded, no more words. Game over")
            return True

        return False

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

        assert self.startNextWord() is True, "Must always be able to start a new word"
        return True

    # ---------------------------------
    # Turn and word management

    def timerExpiredCb(self, ctx):
        """This method is invoked when the timer fires"""
        trace(Level.info, "Timer fired", ctx)

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

        if not self._wordSet.areWordsAvailable(self._usedWordIdxs):
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
        found = self._wordSet.nextWord(self._usedWordIdxs)
        if not found:
            trace(Level.rnd, "Can't start a new turn as no word available")
            # Ran out of words
            return False
        self._usedWordIdxs = found.usedWordIdxs
        secret = found.word
        disallowed = found.disallowed
        trace(Level.rnd, "player", self.activePlayer.name, "word", secret)

        # Create a new Word
        turn = Word(self._curTurnId, nextWordId, secret, disallowed,
                    self.activePlayer, [team for team in self._teams.values()
                                   if team != self.activePlayer.team],
                    self._allConns)
        self._wordsByTurnId[self._curTurnId].append(turn)

        self._curTurn = turn
        return True
