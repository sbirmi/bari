"""Turn manager. Starts new turns etc"""

from collections import defaultdict
from enum import Enum
import random

from fwk.Trace import (
        trace,
        Level,
)
from Taboo.Turn import (
        Turn,
        WordState,
)

class TurnState(Enum):
    START_WAIT = 1
    RUNNING = 2

class TurnManager:
    def __init__(self, txQueue, wordSet, teams, hostNumTurns, allConns):
        self._txQueue = txQueue
        self._wordSet = wordSet
        self._teams = teams
        self._hostNumTurns = hostNumTurns # Stop the game when every live player
                                          # has played hostNumTurns
        self._allConns = allConns

        self._teamCount = len(self._teams)
        self._curTurnId = 0
        self._turnById = defaultdict(list)
        self._curTurn = None

        self._state = TurnState.START_WAIT
        self._usedWordIdxs = set() # index of words used from self._wordSet

    def processMsg(self, qmsg):
        """Handle ALERT, COMPLETED, etc related messages here maybe?"""

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

        if not any(any(True for plyr in plyrs if plyr.turnsPlayed < self._hostNumTurns)
               for plyrs in candidatePlayersByTeam.values()):
            trace(Level.info, "All players have played atleast", self._hostNumTurns, "turns")
            return None


        # Identify current team that's playing
        if self._turnById:
            currentTeam = self._turnById[self._curTurnId][-1].player.team
        else:
            currentTeam = random.choice(list(self._teams.values()))

        # Identify nextPlayer (preferring a player from the next team)
        for teamIdx in [1 + ((ti + currentTeam.teamNumber) % self._teamCount)
                        for ti in range(self._teamCount)]:
            if teamIdx not in candidatePlayersByTeam:
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
        nextPlayer = self._findNextPlayer()
        if not nextPlayer:
            # TODO handle game over here # pylint: disable=fixme
            trace(Level.rnd, "Can't start a new turn as no next player available")
            return False

        # 2. Start a new turn
        self._curTurnId += 1

        return self.startNextWord(nextPlayer)

    def startNextWord(self, activePlayer):
        """
        Returns bool : True if new word started; false if the game is over
                       (no more words available)
        """
        if self._turnById[self._curTurnId]:
            trace(Level.error,
                  "curTurnId", self._curTurnId,
                  "lastWord", self._turnById[self._curTurnId][-1],
                  "Can't start new word when previous word is still IN_PLAY")
            assert self._turnById[self._curTurnId][-1].state != WordState.IN_PLAY

        nextWordId = len(self._turnById[self._curTurnId]) + 1

        # Fetch a new word
        found = self._wordSet.nextWord(self._usedWordIdxs)
        if not found:
            trace(Level.rnd, "Can't start a new turn as no word available")
            # Ran out of words
            return False
        self._usedWordIdxs = found.usedWordIdxs
        secret = found.word
        disallowed = found.disallowed
        trace(Level.rnd, "player", activePlayer.name, "word", secret)

        # Create a new Turn
        turn = Turn(self._curTurnId, nextWordId, secret, disallowed,
                    activePlayer, [team for team in self._teams.values()
                                   if team != activePlayer.team],
                    self._allConns)
        self._turnById[self._curTurnId].append(turn)

        self._curTurn = turn
        return True
