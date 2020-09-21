# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=no-self-use

import asyncio
import unittest

from fwk.LobbyPlugin import plugin
from fwk.Msg import (
        ClientRxMsg,
        ClientTxMsg,
        InternalConnectWsToGi,
        InternalHost,
        InternalGiStatus,
)

class LobbyPluginTest(unittest.TestCase):
    connWs1 = 101
    connWs2 = 102

    def setUp(self):
        self.plugin = plugin()
        self.rxq = asyncio.Queue()
        self.txq = asyncio.Queue()
        self.plugin.setRxTxQueues(self.rxq, self.txq)

    def testInstantiation(self):
        """Test attributes of the plugin"""
        self.assertEqual(self.plugin.path, "lobby")
        self.assertTrue(self.txq.empty())
        self.assertTrue(not self.plugin.giStatusByPath)

    def testHandleHost(self):
        """Handling of HOST message"""
        fakeWs = 1
        msg = ClientRxMsg(["HOST", "foo"], initiatorWs=fakeWs)
        self.plugin.processMsg(msg)

        txmsg = self.txq.get_nowait()
        self.assertIsInstance(txmsg, InternalHost)
        self.assertEqual(txmsg.jmsg, [])
        self.assertEqual(txmsg.path, "foo")
        self.assertEqual(txmsg.initiatorWs, fakeWs)
        self.assertTrue(self.txq.empty())


        msg = ClientRxMsg(["HOST", "bar", {1: 2, 3: 4}], initiatorWs=fakeWs)
        self.plugin.processMsg(msg)

        txmsg = self.txq.get_nowait()
        self.assertIsInstance(txmsg, InternalHost)
        self.assertEqual(txmsg.jmsg, [{1: 2, 3: 4}])
        self.assertEqual(txmsg.path, "bar")
        self.assertEqual(txmsg.initiatorWs, fakeWs)
        self.assertTrue(self.txq.empty())

    def testHandleGiStatusNoConnections(self):
        """Handling of InternalGiStatus"""
        # Add a game with empty status
        msg = InternalGiStatus([], "foo:1")
        self.plugin.processMsg(msg)
        self.assertTrue(self.txq.empty())
        self.assertDictEqual(dict(self.plugin.giStatusByPath), {"foo:1": []})

        # Update existing game
        msg = InternalGiStatus([True], "foo:1")
        self.plugin.processMsg(msg)
        self.assertTrue(self.txq.empty())
        self.assertDictEqual(dict(self.plugin.giStatusByPath),
                             {"foo:1": [True]})

        # Add a different game with non-empty status
        msg = InternalGiStatus([{"count": 10}], "bar:2")
        self.plugin.processMsg(msg)
        self.assertTrue(self.txq.empty())

        self.assertDictEqual(dict(self.plugin.giStatusByPath),
                             {"foo:1": [True],
                              "bar:2": [{"count": 10}]})

    def testHandleGiStatusWithConnections(self):
        """Handling of InternalGiStatus"""
        self.plugin.ws.add(self.connWs1)
        self.plugin.ws.add(self.connWs2)

        # Process InternalGiStatus with two clients connected
        msg = InternalGiStatus([], "foo:1")
        self.plugin.processMsg(msg)

        txMsgs = [self.txq.get_nowait(), self.txq.get_nowait()]
        self.assertListEqual([txm.jmsg for txm in txMsgs],
                             [["GAME-STATUS", "foo:1"], ["GAME-STATUS", "foo:1"]])
        self.assertSetEqual({txm.toWs for txm in txMsgs}, {self.connWs1, self.connWs2})
        self.assertListEqual([txm.initiatorWs for txm in txMsgs], [None, None])
        self.assertTrue(self.txq.empty())

        # Process InternalGiStatus with two clients connected: updating an existing game
        msg = InternalGiStatus([{"count": 10}], "foo:1")
        self.plugin.processMsg(msg)

        txMsgs = [self.txq.get_nowait(), self.txq.get_nowait()]
        self.assertListEqual([txm.jmsg for txm in txMsgs],
                             [["GAME-STATUS", "foo:1", {"count": 10}],
                              ["GAME-STATUS", "foo:1", {"count": 10}]])
        self.assertSetEqual({txm.toWs for txm in txMsgs}, {self.connWs1, self.connWs2})
        self.assertListEqual([txm.initiatorWs for txm in txMsgs], [None, None])
        self.assertTrue(self.txq.empty())

        # Processing same InternalGiStatus with two clients connected
        # should not create messages
        msg = InternalGiStatus([{"count": 10}], "foo:1")
        self.plugin.processMsg(msg)

        self.assertTrue(self.txq.empty())

    def testHandleNewConnection(self):
        """Handling of InternalGiStatus when a new client (connWs2)
        connects when (connWs1) is already connected"""
        self.plugin.giStatusByPath["foo:1"] = [True]

        self.plugin.ws.add(self.connWs1)

        # Process InternalGiStatus with two clients connected
        msg = InternalConnectWsToGi(self.connWs2)
        self.plugin.processMsg(msg)

        txm = self.txq.get_nowait()
        self.assertTrue(self.txq.empty())
        self.assertIsInstance(txm, ClientTxMsg)
        self.assertEqual(txm.jmsg, ["GAME-STATUS", "foo:1", True])
        self.assertEqual(txm.toWs, self.connWs2)
        self.assertEqual(txm.initiatorWs, None)
