# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=no-self-use

import asyncio
import unittest

from test.MsgTestLib import MsgTestLib
from fwk.Msg import ClientTxMsg
from fwk.MsgSrc import (
        Connections,
        MsgSrc,
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
        msgSrc1.setMsgs([[1], [2]], initiatorWs=clientWs3)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([1], {clientWs1}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs1}, initiatorWs=clientWs3)])

        # Adding msgSrc with previous messages
        msgSrc2 = MsgSrc(self.conns)
        msgSrc2.setMsgs([[True], [False]])
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg([True], {clientWs1}),
                                            ClientTxMsg([False], {clientWs1})])

        # Adding a second connection
        self.conns.addConn(clientWs2)
        self.assertGiTxQueueMsgs(self.txq, {ClientTxMsg([1], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs2}, initiatorWs=clientWs3),
                                            ClientTxMsg([True], {clientWs2}, initiatorWs=None),
                                            ClientTxMsg([False], {clientWs2}, initiatorWs=None)})

        # Adding msgSrc with previous messages
        msgSrc2.setMsgs([["yes"]])
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["yes"], {clientWs1, clientWs2})])

        # Delete msgSrc
        self.conns.delMsgSrc(msgSrc2)

        # Add another client
        self.conns.addConn(clientWs3)
        self.assertSetEqual(self.conns.msgSrcs, {msgSrc1})
        self.assertGiTxQueueMsgs(self.txq, {ClientTxMsg([1], {clientWs3}, initiatorWs=clientWs3),
                                            ClientTxMsg([2], {clientWs3}, initiatorWs=clientWs3)})

        # Remove a client
        self.conns.delConn(clientWs2)
        self.assertGiTxQueueMsgs(self.txq, [])

        # Add msgSrc2 again
        self.conns.addMsgSrc(msgSrc2)
        self.assertGiTxQueueMsgs(self.txq, {ClientTxMsg(["yes"], {clientWs1, clientWs3},
                                                        initiatorWs=None)})
