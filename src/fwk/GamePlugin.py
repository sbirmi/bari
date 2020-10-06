"""Defines Plugin -- the base for any plugin that connects to bari.
The Plugin is used as the base for:
1. the main lobby
2. the GameLobbyPlugin (defined here), base for a Game Lobby
3. the GamePlugin (defined here), base for a Game
"""

from fwk.MsgSrc import (
        Connections,
        Jmai,
)
from fwk.Msg import (
        InternalConnectWsToGi,
        InternalDisconnectWsToGi,
        InternalHost,
        ClientRxMsg,
        ClientTxMsg,
)
from fwk.Trace import (
        Level,
        trace,
)


class Plugin:
    """
    Base game instance that is registered with the main loop by the name "path".
    """
    def __init__(self, path, name):
        """
        Arguments
        ---------
        path : str
            Path to reach this instance. For example,
                "lobby"
                "chat"  --  chat room's lobby
                "chat:1"  --  chat room id 1
                "chat:2"  --  chat room id 2
        """
        self.path = path
        self.name = name
        self.rxQueue = None
        self.txQueue = None
        self.conns = None

    # ---------------------------------
    # Startup related

    def postQueueSetup(self):
        """Additional logic to run after RX and TX queues are
        setup for a plugin"""

    def setRxTxQueues(self, rxQueue, txQueue):
        """Setup RX and TX queue for a plugin"""
        assert not self.rxQueue
        assert not self.txQueue
        assert rxQueue
        assert txQueue
        self.rxQueue = rxQueue
        self.txQueue = txQueue
        self.conns = Connections(self.txQueue)
        self.postQueueSetup()


    # ---------------------------------
    # Message sending helpers

    def broadcast(self, jmsg, initiatorWs=None):
        """Send a message to all clients of a Plugin"""
        self.conns.send([Jmai(jmsg, initiatorWs)])

    # ---------------------------------
    # Message handling

    def postProcessConnect(self, ws):
        """Additional logic to run after a ws connects"""

    def processConnect(self, ws):
        """Add client websocket as a member in this game instance"""
        self.conns.addConn(ws)
        self.postProcessConnect(ws)

    def postProcessDisconnect(self, ws):
        """Additional logic to run after a ws disconnects"""

    def processDisconnect(self, ws):
        """Remove client websocket as a member in this game instance"""
        self.conns.delConn(ws)
        self.postProcessDisconnect(ws)

    def processMsg(self, qmsg):
        """Act to on the received msg.

        Return value : bool
            True => msg was handled
            False => msg was handled
        """
        if isinstance(qmsg, InternalConnectWsToGi):
            self.processConnect(qmsg.ws)
            return True

        if isinstance(qmsg, InternalDisconnectWsToGi):
            self.processDisconnect(qmsg.ws)
            return True

        return False

    async def worker(self):
        """The worker task for a plugin. All messages should be processed.
        Any unhandled message returns a bad message to the sender"""
        trace(Level.game, "{}.worker() ready".format(self.path))
        while True:
            qmsg = await self.rxQueue.get()
            self.rxQueue.task_done()
            trace(Level.msg, self.path, "received", str(qmsg))

            processed = self.processMsg(qmsg)
            if not processed:
                if not isinstance(qmsg, ClientRxMsg):
                    trace(Level.error, "Unexpected message not handled:", str(qmsg))
                    continue
                self.txQueue.put_nowait(ClientTxMsg("Bad message", {qmsg.initiatorWs},
                                                    initiatorWs=qmsg.initiatorWs))


class GameLobbyPlugin(Plugin):
    """Base class for a Game Lobby that allows hosting games"""
    def processHost(self, qmsg):
        """A MTYPE_HOST message should be handled here"""
        raise NotImplementedError

    def processMsg(self, qmsg):
        if super(GameLobbyPlugin, self).processMsg(qmsg):
            return True

        if isinstance(qmsg, InternalHost):
            return self.processHost(qmsg)

        return False


class GamePlugin(Plugin):
    """Base class for a Game Instance"""

    def postQueueSetup(self):
        self.publishGiStatus()

    def publishGiStatus(self):
        """Publish this game instance's status to the lobby"""
        raise NotImplementedError
