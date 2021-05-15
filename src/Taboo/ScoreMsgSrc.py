"""SCORE message generator"""

from fwk.MsgSrc import (
        Jmai,
        MsgSrc
)

class ScoreMsgSrc(MsgSrc):
    """Generates score across all turns and sends the
    SCORE message to all clients.

        ["SCORE", {team<int>: score,
                   team<int>: score}]
    """
    def __init__(self, conns, wordsByTurnId, teamIds):
        super(ScoreMsgSrc, self).__init__(conns)
        self._wordsByTurnId = wordsByTurnId
        self._teamIds = teamIds

        self._score = {teamId: 0 for teamId in self._teamIds}
        self.updateTotal()

    @property
    def score(self):
        return self._score

    def updateTotal(self):
        self._score = {teamId: 0 for teamId in self._teamIds}
        for turnWords in self._wordsByTurnId.values():
            for word in turnWords:
                for teamId in word.score:
                    self._score[teamId] += 1

        self.setMsgs([Jmai(["SCORE", self._score], None)])
