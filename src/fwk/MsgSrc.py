"""Infra piece to manage a bunch of source message sources and
websockets.

MsgSrc1 --> +-------------+
            |             | --> WebSocket1
MsgSrc2 --> | Connections |
            |             | --> WebSocket2
MsgSrc3 --> +-------------+

If a new connection is added, last cached messages from
each MsgSrc to the new connection. Any change to MsgSrc
is sent to all websockets.
"""

from collections import namedtuple

from fwk.Msg import ClientTxMsg

Jmai = namedtuple("JmsgAndInitiator", ["jmsg", "initiatorWs"])

class Connections:
    """A collection of websockets and message sources
    (MsgSrc) that are feeding messages to these
    websockets.
    """
    def __init__(self, txQueue):
        self._txQueue = txQueue
        self._msgSrcs = set()
        self._wss = set()

    @property
    def msgSrcs(self):
        """Accessor for internal messages"""
        return self._msgSrcs

    def addMsgSrc(self, msgSrc):
        """Register a new MsgSrc for all websockets"""
        self._msgSrcs.add(msgSrc)
        jmaiList = msgSrc.getMsgs()
        self.send(jmaiList)

    def delMsgSrc(self, msgSrc):
        """Remove a MsgSrc for all websockets"""
        if msgSrc in self._msgSrcs:
            self._msgSrcs.remove(msgSrc)

    def addConn(self, ws):
        """Add a websocket to the set of connections"""
        self._wss.add(ws)
        for msgSrc in self._msgSrcs:
            jmaiList = msgSrc.getMsgs()
            self.send(jmaiList, wss={ws})

    def delConn(self, ws):
        """Remove a websocket from the set of connections"""
        if ws in self._wss:
            self._wss.remove(ws)

    def send(self, jmaiList, wss=None):
        """Send the messages to a subset (or all) connections
        Arguments
        ---------
        jmsgs : list of messages
        initiatorWs : websocket
        wss : (optional) set of websockets
            Websockets to send the messages. If not specified,
            send the message to all websockets.
        """
        wss = wss or self._wss
        if not wss:
            return

        for jmai in jmaiList:
            self._txQueue.put_nowait(ClientTxMsg(jmai.jmsg, wss, initiatorWs=jmai.initiatorWs))

class MsgSrc:
    """A source of messages that needs to be sent to
    all connections.
    """
    def __init__(self, conns):
        self._conns = conns
        self._jmaiList = []
        self._lastInitiatorWs = None
        self._conns.addMsgSrc(self)

    def __del__(self):
        self._conns.delMsgSrc(self)

    def setMsgs(self, jmaiList):
        """Buffer messages each with initiator"""
        self._jmaiList = jmaiList
        self._conns.send(self._jmaiList)

    def getMsgs(self):
        """Get messages and initiator websocket for the messages"""
        return self._jmaiList
