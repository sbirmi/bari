"""Game specific details are tracked here.
"""

from fwk.MsgSrc import Connections
#from Dirty7.Dirty7Round import RoundParameters

class Player:
    def __init__(self, txQueue, name, passwd):
        self.name = name
        self.passwd = passwd
        self.playerConns = Connections(txQueue)
