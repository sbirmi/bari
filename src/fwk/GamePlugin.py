from fwk.Msg import (
        InternalConnectWsToGi,
        InternalDisconnectWsToGi,
        ClientRxMsg,
        ClientTxMsg,
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
        self.ws = set()

    # ---------------------------------
    # Startup related

    def queueSetupComplete(self):
        pass

    def setRxTxQueues(self, rxQueue, txQueue):
        assert not self.rxQueue
        assert not self.txQueue
        assert rxQueue
        assert txQueue
        self.rxQueue = rxQueue
        self.txQueue = txQueue
        self.queueSetupComplete()


    # ---------------------------------
    # Message sending helpers

    def broadcast(self, jmsg, initiatorWs=None):
        for toWs in self.ws:
            self.txQueue.put_nowait(
                    ClientTxMsg(jmsg, toWs,
                        initiatorWs=initiatorWs))

    # ---------------------------------
    # Message handling

    def processConnect(self, ws):
        """Add client websocket as a member in this game instance"""
        self.ws.add(ws)

    def processDisconnect(self, ws):
        """Remove client websocket as a member in this game instance"""
        self.ws.remove(ws)

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
        print("{}.worker() ready".format(self.path))
        while True:
            qmsg = await self.rxQueue.get()
            self.rxQueue.task_done()
            print("{}.worker() received".format(self.path), qmsg)

            processed = self.processMsg(qmsg)
            if not processed:
                if not isinstance(qmsg, ClientRxMsg):
                    print("Unexpected message not handled:", qmsg)
                    continue
                self.txQueue.put_nowait(ClientTxMsg("Bad message", qmsg.initiatorWs,
                                                    initiatorWs=qmsg.initiatorWs))
