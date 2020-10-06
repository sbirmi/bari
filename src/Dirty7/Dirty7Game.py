"""Game specific details are tracked here.
"""

from fwk.MsgSrc import Connections

class GameStateBase:
    def toJmsg(self):
        return str(self)

    def __str__(self):
        assert self.__class__.__name__.startswith("State")
        return self.__class__.__name__[5:]


class StateWaitingForPlayers(GameStateBase):
    pass

class StateGameBegin(GameStateBase):
    pass

class StateRoundStart(GameStateBase):
    pass

class StatePlayerTurn(GameStateBase):
    pass

class StateRoundStop(GameStateBase):
    pass

class StateGameOver(GameStateBase):
    pass

class Player:
    def __init__(self, txQueue, name, passwd):
        self.name = name
        self.passwd = passwd
        self.playerConns = Connections(txQueue)
