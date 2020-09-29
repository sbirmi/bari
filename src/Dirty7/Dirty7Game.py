"""Game specific details are tracked here.
"""

from fwk.MsgSrc import Connections
#from Dirty7.Dirty7Round import RoundParameters

class GameState:
    WAITING_FOR_PLAYERS = 1
    ROUND_START = 2
    PLAYER_TURN = 3
    ROUND_STOP = 4
    GAME_OVER = 5

class Player:
    def __init__(self, txQueue, name, passwd):
        self.name = name
        self.passwd = passwd
        self.playerConns = Connections(txQueue)
