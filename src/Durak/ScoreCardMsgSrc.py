from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)

class ScoreCardMsgSrc(MsgSrc):
    """
    ["SCORE",
     score-per-round, # roundNum --> player --> score collected
     total-score, # playerName --> score
    ]
    """
    def __init__(self, conns, playerNames):
        super(ScoreCardMsgSrc, self).__init__(conns)
        self.playerNames = playerNames

        self.scoreByPlayerByRound = {}
        self.totalScore = {name: 0 for name in self.playerNames}

        self.refresh()

    def setRoundLosers(self, roundNum, losers):
        self.scoreByPlayerByRound[roundNum] = {
            player: 1 if player in losers else 0
            for player in self.playerNames
        }
        for name in losers:
            self.totalScore[name] += 1

        self.refresh()

    def refresh(self):
        self.setMsgs([Jmai(["SCORE", self.scoreByPlayerByRound, self.totalScore], None)])

    def playersReachedScore(self, targetScore):
        return {player for player, score in self.totalScore.items()
                if score >= targetScore}
