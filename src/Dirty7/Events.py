class EventBase:
    def __str__(self):
        raise NotImplementedError

    def toJmsg(self):
        return []

class PlayerJoin(EventBase):
    def __init__(self, player):
        self.player = player

    def __str__(self):
        return self.player.name + " joined"

class StartRound(EventBase):
    def __init__(self, roundNum, turnOrderNames, turnIdx=0):
        self.roundNum = roundNum
        self.turnOrderNames = turnOrderNames
        self.turnIdx = turnIdx

    def __str__(self):
        return "Start round {} turnOrderNames {} turnIdx {}".format(self.roundNum,
                                                                    self.turnOrderNames,
                                                                    self.turnIdx)

class AdvanceTurn(EventBase):
    def __init__(self, turnStep):
        self.turnStep = turnStep

    def toJmsg(self):
        return [{"AdvanceTurn": self.turnStep}]

    def __str__(self):
        return "Advance turn {}".format(self.turnStep)

class StopRound(EventBase):
    def __init__(self, roundNum):
        self.roundNum = roundNum

    def __str__(self):
        return "Stop round {}".format(self.roundNum)

class GameBegin(EventBase):
    def __str__(self):
        return "Game begin"

class GameOver(EventBase):
    def __str__(self):
        return "Game over"

class Declare(EventBase):
    def __init__(self, player, score):
        self.player = player
        self.score = score

    def __str__(self):
        return "Declare by " + self.player.name + " at %d points" % self.score

    def toJmsg(self):
        return [self.player.name, self.score]
