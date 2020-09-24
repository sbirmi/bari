# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=no-self-use

import asyncio
import unittest

from Chat.ChatRoom import ChatRoom
from fwk.Msg import (
        ClientRxMsg,
        ClientTxMsg,
        InternalConnectWsToGi,
        InternalDisconnectWsToGi,
        InternalGiStatus,
)

class ChatRoomTest(unittest.TestCase):
    connWs1 = 101
    connWs2 = 102

    def setUp(self):
        self.plugin = ChatRoom("chat:1", "Chat Room 1")
        self.rxq = asyncio.Queue()
        self.txq = asyncio.Queue()
        self.plugin.setRxTxQueues(self.rxq, self.txq)

    def testInstantiation(self):
        """Test attributes of the plugin"""
        txmsg = self.txq.get_nowait()
        self.assertIsInstance(txmsg, InternalGiStatus)
        self.assertEqual(txmsg.fromPath, "chat:1")
        self.assertListEqual(txmsg.jmsg, [{"clients": 0}])
        self.assertTrue(self.txq.empty())

    def testHandleConnection(self):
        """InternalGiStatus is sent when websockets connect/disconnect
        from ChatRoom"""
        self.testInstantiation()

        # Connect a websocket
        msg = InternalConnectWsToGi(self.connWs1)
        self.plugin.processMsg(msg)

        txmsg = self.txq.get_nowait()
        self.assertIsInstance(txmsg, InternalGiStatus)
        self.assertEqual(txmsg.fromPath, "chat:1")
        self.assertEqual(txmsg.initiatorWs, None)
        self.assertListEqual(txmsg.jmsg, [{'clients': 1}])
        self.assertTrue(self.txq.empty())

        # Disconnect a websocket
        msg = InternalDisconnectWsToGi(self.connWs1)
        self.plugin.processMsg(msg)

        txmsg = self.txq.get_nowait()
        self.assertIsInstance(txmsg, InternalGiStatus)
        self.assertEqual(txmsg.fromPath, "chat:1")
        self.assertEqual(txmsg.initiatorWs, None)
        self.assertListEqual(txmsg.jmsg, [{'clients': 0}])
        self.assertTrue(self.txq.empty())

    def testHandleMsg(self):
        """Handling of InternalGiStatus"""
        self.testInstantiation()

        self.plugin.ws.add(self.connWs1)
        self.plugin.ws.add(self.connWs2)

        fakeWs = 55
        msg = ClientRxMsg(["foo", 2, True, {"count": 3}], initiatorWs=fakeWs)
        self.plugin.processMsg(msg)
        txmsg = self.txq.get_nowait()
        self.assertIsInstance(txmsg, ClientTxMsg)
        self.assertEqual(txmsg.jmsg, ["foo", 2, True, {"count": 3}])
        self.assertEqual(txmsg.initiatorWs, fakeWs)
        self.assertSetEqual(txmsg.toWss, {self.connWs1, self.connWs2})
        self.assertTrue(self.txq.empty())
