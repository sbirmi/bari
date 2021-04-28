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

class ConnectionsBase:
    def __init__(self, txQueue):
        self._txQueue = txQueue
        self._msgSrcs = set()

    @property
    def msgSrcs(self):
        """Accessor for internal messages"""
        return self._msgSrcs

    def addMsgSrc(self, msgSrc):
        """Register a new MsgSrc for all websockets"""
        self._msgSrcs.add(msgSrc)

    def delMsgSrc(self, msgSrc):
        """Remove a MsgSrc for all websockets"""
        if msgSrc in self._msgSrcs:
            self._msgSrcs.remove(msgSrc)

    def count(self):
        """Number of connections tracked"""
        raise NotImplementedError

    def send(self, jmaiList, wss=None):
        """Send the messages to a subset (or all) connections
        Arguments
        ---------
        jmsgs : list of messages
        wss : (optional) set of websockets
            Websockets to send the messages. If not specified,
            send the message to all websockets.
        """
        raise NotImplementedError

class Connections(ConnectionsBase):
    """A collection of websockets and message sources
    (MsgSrc) that are feeding messages to these
    websockets.
    """
    def __init__(self, txQueue):
        super(Connections, self).__init__(txQueue)
        self._wss = set()

    def addMsgSrc(self, msgSrc):
        """Register a new MsgSrc for all websockets"""
        ConnectionsBase.addMsgSrc(self, msgSrc)
        jmaiList = msgSrc.getMsgs()
        self.send(jmaiList)

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

    def count(self):
        """Number of connections being tracked"""
        return len(self._wss)

    def send(self, jmaiList, wss=None):
        """Send the messages to a subset (or all) connections
        Arguments
        ---------
        jmsgs : list of messages
        wss : (optional) set of websockets
            Websockets to send the messages. If not specified,
            send the message to all websockets.
        """
        wss = wss or self._wss
        if not wss:
            return

        for jmai in jmaiList:
            self._txQueue.put_nowait(ClientTxMsg(jmai.jmsg, wss, initiatorWs=jmai.initiatorWs))

class ConnectionsGroup(ConnectionsBase):
    """ConnectionsGroup allows collecting multiple Connections as
    a single Connections instance for the purposes of messaging.

                    ConnectionsGroup
    MsgSrc1 --> +---------------------+
                |       Connections1  | --> WebSocket1
    MsgSrc2 --> |                     |
                |       Connections2  | --> WebSocket2, WebSocket3, ...
    MsgSrc3 --> +---------------------+

    """
    def __init__(self):
        super(ConnectionsGroup, self).__init__(None)
        self._conns = set()

    def addMsgSrc(self, msgSrc):
        """Register a new MsgSrc for all websockets"""
        ConnectionsBase.addMsgSrc(self, msgSrc)
        for conn in self._conns:
            conn.addMsgSrc(msgSrc)

    def delMsgSrc(self, msgSrc):
        """Remove a MsgSrc for all websockets"""
        if msgSrc in self._msgSrcs:
            self._msgSrcs.remove(msgSrc)
            for conn in self._conns:
                conn.delMsgSrc(msgSrc)

    def addConnections(self, conn):
        self._conns.add(conn)
        for msgSrc in self._msgSrcs:
            conn.addMsgSrc(msgSrc)

    def delConnections(self, conn):
        if conn in self._conns:
            self._conns.remove(conn)
            for msgSrc in self._msgSrcs:
                conn.delMsgSrc(msgSrc)

    def count(self):
        return sum(conn for conn in self._conns)

    def send(self, jmaiList, conns=None): # pylint: disable=arguments-differ
        """Send the messages to all connections within all conns
        Arguments
        ---------
        jmsgs : list of messages
        """
        for conn in conns or self._conns:
            conn.send(jmaiList)

class MsgSrc:
    """A source of messages that needs to be sent to
    all connections.
    """
    def __init__(self, conns):
        self._conns = conns
        self._jmaiList = []
        self._conns.addMsgSrc(self)

    def __del__(self):
        self._conns.delMsgSrc(self)

    def addMsgs(self, jmaiList):
        self._jmaiList.append(jmaiList)
        self._conns.send(jmaiList)

    def replaceMsg(self, idx, jmai):
        self._jmaiList[idx] = jmai
        self._conns.send([jmai])

    def setMsgs(self, jmaiList):
        """Buffer messages each with initiator"""
        self._jmaiList = jmaiList
        self._conns.send(self._jmaiList)

    def getMsgs(self):
        """Get messages and initiator websocket for the messages"""
        return self._jmaiList
