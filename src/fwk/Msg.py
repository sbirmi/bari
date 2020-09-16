"""Basic message definitions passed within bari"""

# pylint: disable=too-few-public-methods
# pylint: disable=missing-class-docstring

class Msg:
    pass

class MsgToPath(Msg):
    def __init__(self, path, jmsg):
        self.path = path
        self.jmsg = jmsg

class MsgFromWs(Msg):
    def __init__(self, ws, jmsg):
        self.ws = ws
        self.jmsg = jmsg

class MsgToWs(Msg):
    def __init__(self, ws, jmsg):
        self.ws = ws
        self.jmsg = jmsg

class InternalRegisterGiMsg(Msg):
    def __init__(self, gi):
        self.gi = gi

class InternalConnectWsToGi(Msg):
    def __init__(self, ws):
        self.ws = ws

class InternalDisconnectWsToGi(Msg):
    def __init__(self, ws):
        self.ws = ws
