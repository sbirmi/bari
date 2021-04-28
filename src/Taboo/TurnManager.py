"""Turn manager. Starts new turns etc"""

from collections import defaultdict

from Taboo.Turn import Turn

class TurnManager:
    def __init__(self, txQueue, wordSrc, teams, allConns):
        self.txQueue = txQueue
        self.wordSrc = wordSrc
        self.teams = teams
        self.allConns = allConns

        self.curTurnIdx = 0
        self.turnByIdx = defaultdict(list)

    def processMsg(self, qmsg):
        """Handle ALERT, COMPLETED, etc related messages here maybe?"""
