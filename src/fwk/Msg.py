"""Basic message definitions passed within bari."""

# pylint: disable=too-few-public-methods
# pylint: disable=missing-class-docstring

class MsgBase:
    def __init__(self, initiatorWs=None):
        """initiatorWs is non None when the message is directly or
        indirectly initiated by a websocket (the one you would
        want to eventually notify about failure to do what
        was requested). When set to None, it is generated
        internally as an update
        """
        self.initiatorWs = initiatorWs

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return str(self).__hash__()

    def __str__(self):
        """Each message must have a unique representation of the content.
        This function is used to implement Msg comparison"""
        # pylint: disable=bad-super-call
        return self.__class__.__name__ + ": initiatorWs=" + str(self.initiatorWs)

class ClientRxMsg(MsgBase):
    def __init__(self, jmsg, initiatorWs):
        """A message received from the client"""
        super(ClientRxMsg, self).__init__(initiatorWs=initiatorWs)
        self.jmsg = jmsg

    def __str__(self):
        # pylint: disable=bad-super-call
        return super(self.__class__, self).__str__() + " jmsg=" + str(self.jmsg)

class ClientTxMsg(MsgBase):
    def __init__(self, jmsg, toWss, initiatorWs=None):
        super(ClientTxMsg, self).__init__(initiatorWs=initiatorWs)
        self.toWss = toWss
        self.jmsg = jmsg

    def __str__(self):
        # pylint: disable=bad-super-call
        return (super(self.__class__, self).__str__() +
                " toWss=" + ",".join(str(w) for w in self.toWss) +
                " jmsg=" + str(self.jmsg))

class InternalRegisterGi(MsgBase):
    def __init__(self, gi, initiatorWs=None):
        super(InternalRegisterGi, self).__init__(initiatorWs=initiatorWs)
        self.gi = gi

    def __str__(self):
        # pylint: disable=bad-super-call
        return super(self.__class__, self).__str__() + " gi=" + str(self.gi)

class InternalConnectWsToGi(MsgBase):
    def __init__(self, ws):
        super(InternalConnectWsToGi, self).__init__(initiatorWs=ws)
        self.ws = ws

class InternalDisconnectWsToGi(MsgBase):
    def __init__(self, ws):
        super(InternalDisconnectWsToGi, self).__init__(initiatorWs=ws)
        self.ws = ws

class InternalHost(MsgBase):
    """These should only be created from the lobby.
    The jmsg is opaque to the lobby."""
    def __init__(self, jmsg, path, initiatorWs=None):
        super(InternalHost, self).__init__(initiatorWs=initiatorWs)
        self.jmsg = jmsg
        self.path = path

    def __str__(self):
        # pylint: disable=bad-super-call
        return super(self.__class__, self).__str__() + " jmsg=" + str(self.jmsg) + \
                " path=" + self.path

class InternalGiStatus(MsgBase):
    """These are targeted for the lobby.
    This contains the JSON message representation the
    current state of the game. The message is opaque to
    the lobby as it may contain game specific details.
    """
    def __init__(self, jmsg, fromPath):
        super(InternalGiStatus, self).__init__(initiatorWs=None)
        self.fromPath = fromPath
        self.jmsg = jmsg

    def __str__(self):
        # pylint: disable=bad-super-call
        return super(self.__class__, self).__str__() + " jmsg=" + str(self.jmsg) + \
                " fromPath=" + self.fromPath
