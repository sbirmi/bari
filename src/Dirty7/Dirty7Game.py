"""Game specific details are tracked here.
"""

from fwk.MsgSrc import Connections

class GameState:
    WAITING_FOR_PLAYERS = 1
    GAME_BEGIN = 2
    ROUND_START = 3
    PLAYER_TURN = 4
    ROUND_STOP = 5
    GAME_OVER = 6

class Player:
    def __init__(self, txQueue, name, passwd):
        self.name = name
        self.passwd = passwd
        self.playerConns = Connections(txQueue)
