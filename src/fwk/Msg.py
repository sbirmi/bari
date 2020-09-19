"""Basic message definitions passed within bari"""

# pylint: disable=too-few-public-methods
# pylint: disable=missing-class-docstring

class Msg:
#    def __init__(self, fromWs):
#        """fromWs is non None when the message is initiated by
#        a websocket and a possible failure message needs to be
#        sent back to the websocket"""
#        self.fromWs = fromWs
    pass

#class MsgToPath(Msg):
#    def __init__(self, path, jmsg, fromWs=None):
#        self.path = path
#        self.jmsg = jmsg
#        self.fromWs = fromWs

class MsgFromWs(Msg):
    def __init__(self, ws, jmsg):
        self.ws = ws
        self.jmsg = jmsg

class MsgToWs(Msg):
    def __init__(self, ws, jmsg):
        self.ws = ws
        self.jmsg = jmsg

class InternalRegisterGi(Msg):
    def __init__(self, gi):
        self.gi = gi

class InternalConnectWsToGi(Msg):
    def __init__(self, ws):
        self.ws = ws

class InternalDisconnectWsToGi(Msg):
    def __init__(self, ws):
        self.ws = ws

class InternalHost(Msg):
    """These should only be created from the lobby.
    The jmsg is opaque to the lobby."""
    def __init__(self, path, fromWs, jmsg):
        self.path = path
        self.fromWs = fromWs
        self.jmsg = jmsg

class InternalGiStatus(Msg):
    """These are targeted for the lobby.
    This contains the JSON message representation the
    current state of the game. The message is opaque to
    the lobby as it may contain game specific details.
    """
    def __init__(self, fromPath, jmsg):
        self.fromPath = fromPath
        self.jmsg = jmsg
