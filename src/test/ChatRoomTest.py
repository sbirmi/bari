# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=no-self-use

import asyncio
import unittest

from test.MsgTestLib import MsgTestLib
from Chat.ChatRoom import ChatRoom
from fwk.Msg import (
        ClientRxMsg,
        ClientTxMsg,
        InternalConnectWsToGi,
        InternalDisconnectWsToGi,
        InternalGiStatus,
)

class ChatRoomTest(unittest.TestCase, MsgTestLib):
    connWs1 = 101
    connWs2 = 102

    def setUp(self):
        self.plugin = ChatRoom("chat:1", "Chat Room 1")
        self.rxq = asyncio.Queue()
        self.txq = asyncio.Queue()
        self.plugin.setRxTxQueues(self.rxq, self.txq)

    def testInstantiation(self):
        """Test attributes of the plugin"""
        self.assertGiTxQueueMsgs(self.txq, [InternalGiStatus([{"clients": 0}], "chat:1")])

    def testHandleConnection(self):
        """InternalGiStatus is sent when websockets connect/disconnect
        from ChatRoom"""
        self.testInstantiation()

        # Connect a websocket
        msg = InternalConnectWsToGi(self.connWs1)
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [InternalGiStatus([{"clients": 1}], "chat:1")])

        # Disconnect a websocket
        msg = InternalDisconnectWsToGi(self.connWs1)
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [InternalGiStatus([{"clients": 0}], "chat:1")])

    def testHandleMsg(self):
        """Received messages are broadcast to all clients"""
        self.testInstantiation()

        self.plugin.ws.add(self.connWs1)
        self.plugin.ws.add(self.connWs2)

        fakeWs = 55
        msg = ClientRxMsg(["foo", 2, True, {"count": 3}], initiatorWs=fakeWs)
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["foo", 2, True, {"count": 3}],
                                                        {self.connWs1, self.connWs2},
                                                        initiatorWs=fakeWs)])
