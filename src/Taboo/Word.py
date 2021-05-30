"""Represents a single Word in a Turn in Taboo"""

from enum import Enum

from fwk.MsgSrc import (
        ConnectionsGroup,
        Jmai,
        MsgSrc,
)
from fwk.Trace import (
        trace,
        Level,
)

class WordState(Enum):
    IN_PLAY = 1
    COMPLETED = 2
    DISCARDED = 3
    TIMED_OUT = 4

class Word:
    def __init__(self, turnId, wordId,
                 secret, disallowed,
                 player, otherTeams, allConns,
                 utcTimeout,
                 state=WordState.IN_PLAY,
                 score=None):
        self._turnId = turnId
        self._wordId = wordId
        self._secret = secret
        self._disallowed = disallowed
        self._player = player
        self._otherTeams = otherTeams
        self._utcTimeout = utcTimeout
        self._state = state
        self._score = score or [] # list of teamNumbers that should be awarded points

        trace(Level.rnd, "New Word", str(self))

        # Messages are broadcast to everyone connected to the room
        self._publicMsgSrc = MsgSrc(allConns)

        # If we are in play, we have to send private messages revealing
        # The word in play to some people
        self._privateMsgSrc = None
        if state == WordState.IN_PLAY:
            privateConnsGrp = ConnectionsGroup()
            privateConnsGrp.addConnections(self._player.playerConns)
            for team in self._otherTeams:
                privateConnsGrp.addConnections(team.conns)
            self._privateMsgSrc = MsgSrc(privateConnsGrp)

        self.updateMsgs()

    def __str__(self):
        return "Word({},{}) player={} secret={} state={} score={}".format(
                self._turnId, self._wordId,
                self._player.name,
                self._secret,
                self._state,
                self._score)

    @property
    def player(self):
        return self._player

    @property
    def state(self):
        return self._state

    @property
    def wordId(self):
        return self._wordId

    @property
    def score(self):
        return self._score

    def updateMsgs(self):
        """Figures out what messages to send to who based on internal state"""
        if self._state == WordState.IN_PLAY:
            assert self._privateMsgSrc

            msg1 = ["TURN", self._turnId, self._wordId,
                    {"team": self._player.team.teamNumber,
                     "player": self._player.name,
                     "state": self._state.name,
                     "utcTimeout": self._utcTimeout}]
            self._publicMsgSrc.setMsgs([Jmai(msg1, None)])

            msg2 = msg1[:] # make a copy of msg1
            msg2[3] = dict(msg1[3]) # Make a copy of the dict (and don't update
                                    # the dictionary in msg1)
            msg2[3].update({
                "secret": self._secret,
                "disallowed": self._disallowed,
            })
            self._privateMsgSrc.setMsgs([Jmai(msg2, None)])

            return

        # If the turn isn't in play, there is no private messaging needed.
        if self._privateMsgSrc:
            self._privateMsgSrc.setMsgs([]) # Reset previous messages
            self._privateMsgSrc = None

        msg = ["TURN", self._turnId, self._wordId,
               {"team": self._player.team.teamNumber,
                "player": self._player.name,
                "state": self._state.name,
                "secret": self._secret,
                "disallowed": self._disallowed,
                "score": self._score}]
        self._publicMsgSrc.setMsgs([Jmai(msg, None)])

    def resolve(self, state):
        """Resolve the word as DISCARDED, COMPLETED, or TIMED_OUT"""
        trace(Level.play, "state", state.name)
        if state == WordState.COMPLETED:
            self._score = [self._player.team.teamNumber]
        elif state == WordState.DISCARDED:
            self._score = [team.teamNumber for team in self._otherTeams]
        elif state == WordState.TIMED_OUT:
            self._score = []
        self._state = state
        self.updateMsgs()
