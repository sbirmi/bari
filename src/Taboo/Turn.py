"""Represents a single Turn in Taboo"""

from enum import Enum

from fwk.MsgSrc import (
        ConnectionsGroup,
        Jmai,
        MsgSrc,
)

class TurnState(Enum):
    IN_PLAY = 1
    COMPLETED = 2
    DISCARDED = 3
    TIMED_OUT = 4

class Turn:
    def __init__(self, turnIdx, wordIdx,
                 secret, disallowed,
                 player, otherTeams, allConns,
                 state=TurnState.IN_PLAY,
                 score=None):
        self.turnIdx = turnIdx
        self.wordIdx = wordIdx
        self.secret = secret
        self.disallowed = disallowed
        self.player = player
        self.otherTeams = otherTeams
        self.allConns = allConns
        self.state = state
        self.score = score or [] # list of teamNumbers that should be awarded points

        # Messages are broadcast to everyone connected to the room
        self.publicMsgSrc = MsgSrc(self.allConns)

        # If we are in play, we have to send private messages revealing
        # The word in play to some people
        self.privateMsgSrc = None
        if state == TurnState.IN_PLAY:
            self.privateConnsGrp = ConnectionsGroup()
            self.privateConnsGrp.addConnections(self.player.playerConns)
            for team in self.otherTeams:
                self.privateConnsGrp.addConnections(team.conns)
            self.privateMsgSrc = MsgSrc(self.privateConnsGrp)

        self.updateMsgs()

    def updateMsgs(self):
        """Figures out what messages to send to who based on internal state"""
        if self.state == TurnState.IN_PLAY:
            assert self.privateMsgSrc

            msg1 = ["TURN", self.turnIdx, self.wordIdx,
                    {"team": self.player.team.teamNumber,
                     "player": self.player.name,
                     "state": self.state.name}]
            self.publicMsgSrc.setMsgs([Jmai(msg1, None)])

            msg2 = msg1[:] # make a copy of msg1
            msg2[3] = dict(msg1[3]) # Make a copy of the dict (and don't update
                                    # the dictionary in msg1)
            msg2[3].update({
                "secret": self.secret,
                "disallowed": self.disallowed,
            })
            self.privateMsgSrc.setMsgs([Jmai(msg2, None)])

            return

        # If the word isn't in play, there is no private messaging needed.
        if self.privateMsgSrc:
            self.privateConnsGrp = None
            self.privateMsgSrc = None

        msg = ["TURN", self.turnIdx, self.wordIdx,
               {"team": self.player.team.teamNumber,
                "player": self.player.name,
                "state": self.state.name,
                "secret": self.secret,
                "disallowed": self.disallowed,
                "score": self.score}]
        self.publicMsgSrc.setMsgs([Jmai(msg, None)])
