# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

import asyncio
import unittest

from test.MsgTestLib import MsgTestLib
from fwk.Msg import ClientTxMsg
from fwk.MsgSrc import (
        Connections,
        ConnectionsGroup,
        MsgSrc,
        Jmai,
)

clientWs1 = 101
clientWs2 = 102
clientWs3 = 103

class MsgSrcConnectionsTest(unittest.TestCase, MsgTestLib):
    """Test MsgSrc and Connections

    MsgSrc1 --> +-------------+
                |             | --> Websocket1
    MsgSrc2 --> | Connections |
                |             | --> Websocket2
    MsgSrc3 --> +-------------+
    """
    def setUp(self):
        self.txq = asyncio.Queue()
        self.conns = Connections(self.txq)

    def test1MsgSrc1Websocket(self):
        """
        Try various triggers of adding/removing MsgSrcs and Websockets
        """
        self.assertGiTxQueueMsgs(self.txq, [])

        # Adding connections doesn't create a message
        self.conns.addConn(clientWs1)
        self.assertGiTxQueueMsgs(self.txq, [])

        # Adding msgSrc with no messages
        msgSrc1 = MsgSrc(self.conns)
        self.assertGiTxQueueMsgs(self.txq, [])

        # Set messages in msgSrc
        msgSrc1.setMsgs([Jmai([1], initiatorWs=clientWs3),
                         Jmai([2], initiatorWs=clientWs3)])
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs1}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs1}, initiatorWs=clientWs3)])

        # Adding msgSrc with previous messages
        msgSrc2 = MsgSrc(self.conns)
        msgSrc2.setMsgs([Jmai([True], initiatorWs=None),
                         Jmai([False], initiatorWs=None)])
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([True], {clientWs1}),
                                            ClientTxMsg([False], {clientWs1})])

        # Adding a second connection
        self.conns.addConn(clientWs2)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([True], {clientWs2}, initiatorWs=None),
                                            ClientTxMsg([False], {clientWs2}, initiatorWs=None)],
                                 anyOrder=True)

        # Adding msgSrc with state preset
        msgSrc2.setMsgs([Jmai(["yes"], initiatorWs=None)])
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["yes"], {clientWs1, clientWs2})])

        # Delete msgSrc
        self.conns.delMsgSrc(msgSrc2)

        # Add another client
        self.conns.addConn(clientWs3)
        self.assertSetEqual(self.conns.msgSrcs, {msgSrc1})
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs3}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs3}, initiatorWs=clientWs3)],
                                 anyOrder=True)

        # Remove a client
        self.conns.delConn(clientWs2)
        self.assertGiTxQueueMsgs(self.txq, [])

        # Add msgSrc2 again
        self.conns.addMsgSrc(msgSrc2)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["yes"], {clientWs1, clientWs3},
                                                        initiatorWs=None)],
                                 anyOrder=True)

class MsgSrcConnectionsGroupTest(unittest.TestCase, MsgTestLib):
    """Test MsgSrc and Connections

                    ConnectionsGroup
    MsgSrc1 --> +---------------------+
                |       Connections1  | --> WebSocket1
    MsgSrc2 --> |                     |
                |       Connections2  | --> WebSocket2, +WebSocket3
    MsgSrc3 --> +---------------------+
    """
    def setUp(self):
        self.txq = asyncio.Queue()
        self.conns = ConnectionsGroup()

    def testNoMessagesInitially(self):
        self.assertGiTxQueueMsgs(self.txq, [])
        self.assertEqual(self.conns.count(), 0)

    def testAddConnectionsBeforeMsgSrc(self):
        conns1 = Connections(self.txq)
        conns2 = Connections(self.txq)
        conns2.addConn(clientWs2)

        self.assertGiTxQueueMsgs(self.txq, [])

        self.conns.addConnections(conns1)
        self.assertGiTxQueueMsgs(self.txq, [])

        self.conns.addConnections(conns2)
        self.assertGiTxQueueMsgs(self.txq, [])

        # Add message sources

        # message source with no messages
        msgSrcEmpty = MsgSrc(self.conns) # pylint: disable=unused-variable
        self.assertGiTxQueueMsgs(self.txq, [])

        msgSrc = MsgSrc(self.conns)
        msgSrc.setMsgs([Jmai([1], initiatorWs=clientWs3),
                        Jmai([2], initiatorWs=clientWs3)])
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs2}, initiatorWs=clientWs3)])

    def testAddConnectionsAfterMsgSrc(self):
        # message source with no messages
        msgSrcEmpty = MsgSrc(self.conns) # pylint: disable=unused-variable


        msgSrc = MsgSrc(self.conns)
        msgSrc.setMsgs([Jmai([1], initiatorWs=clientWs3),
                        Jmai([2], initiatorWs=clientWs3)])

        self.assertGiTxQueueMsgs(self.txq, [])

        # Add websockets afterwards

        conns1 = Connections(self.txq)
        conns2 = Connections(self.txq)
        conns2.addConn(clientWs2)

        self.conns.addConnections(conns1)
        self.assertGiTxQueueMsgs(self.txq, [])

        self.conns.addConnections(conns2)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs2}, initiatorWs=clientWs3)])

        conns1.addConn(clientWs1)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs1}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs1}, initiatorWs=clientWs3)])

    def testAddDelConnections(self):
        conns1 = Connections(self.txq)
        conns1.addConn(clientWs1)
        conns2 = Connections(self.txq)
        conns2.addConn(clientWs2)

        self.conns.addConnections(conns1)
        self.conns.addConnections(conns2)

        msgSrc = MsgSrc(self.conns)
        msgSrc.setMsgs([Jmai([1], initiatorWs=clientWs3),
                        Jmai([2], initiatorWs=clientWs3)])


        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs1}, initiatorWs=clientWs3),
                                            ClientTxMsg([1], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs1}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs2}, initiatorWs=clientWs3)],
                                 anyOrder=True)

        self.conns.delConnections(conns1)

        clientWs4 = 104
        conns3 = Connections(self.txq)
        conns3.addConn(clientWs3)
        conns3.addConn(clientWs4)

        self.conns.addConnections(conns3)

        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs3, clientWs4},
                                                        initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs3, clientWs4},
                                                        initiatorWs=clientWs3)],
                                 anyOrder=True)
