# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

import asyncio
import unittest

from test.MsgTestLib import MsgTestLib
from fwk.LobbyPlugin import plugin
from fwk.Msg import (
        ClientRxMsg,
        ClientTxMsg,
        InternalConnectWsToGi,
        InternalHost,
        InternalGiStatus,
)

class LobbyPluginTest(unittest.TestCase, MsgTestLib):
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
        self.assertGiTxQueueMsgs(self.txq, [])
        self.assertTrue(not self.plugin.giStatusByPath)

    def testHandleHost(self):
        """Handling of HOST message"""
        fakeWs = 1
        msg = ClientRxMsg(["HOST", "foo"], initiatorWs=fakeWs)
        self.plugin.processMsg(msg)

        self.assertGiTxQueueMsgs(self.txq, [InternalHost([], "foo", initiatorWs=fakeWs)])

        msg = ClientRxMsg(["HOST", "bar", {1: 2, 3: 4}], initiatorWs=fakeWs)
        self.plugin.processMsg(msg)

        self.assertGiTxQueueMsgs(self.txq, [InternalHost([{1: 2, 3: 4}], "bar",
                                                         initiatorWs=fakeWs)])

    def testHandleGiStatusNoConnections(self):
        """Handling of InternalGiStatus"""
        # Add a game with empty status
        msg = InternalGiStatus([], "foo:1")
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [])
        self.assertDictEqual(dict(self.plugin.giStatusByPath), {"foo:1": []})

        # Update existing game
        msg = InternalGiStatus([True], "foo:1")
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [])
        self.assertDictEqual(dict(self.plugin.giStatusByPath),
                             {"foo:1": [True]})

        # Add a different game with non-empty status
        msg = InternalGiStatus([{"count": 10}], "bar:2")
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [])

        self.assertDictEqual(dict(self.plugin.giStatusByPath),
                             {"foo:1": [True],
                              "bar:2": [{"count": 10}]})

    def testHandleGiStatusWithConnections(self):
        """Handling of InternalGiStatus"""
        self.plugin.conns.addConn(self.connWs1)
        self.plugin.conns.addConn(self.connWs2)

        # Process InternalGiStatus with two clients connected
        msg = InternalGiStatus([], "foo:1")
        self.plugin.processMsg(msg)

        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["GAME-STATUS", "foo:1"],
                                                        {self.connWs1, self.connWs2},
                                                        initiatorWs=None)])

        # Process InternalGiStatus with two clients connected: updating an existing game
        msg = InternalGiStatus([{"count": 10}], "foo:1")
        self.plugin.processMsg(msg)

        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["GAME-STATUS", "foo:1", {"count": 10}],
                                                        {self.connWs1, self.connWs2},
                                                        initiatorWs=None)])

        # Processing same InternalGiStatus with two clients connected
        # should not create messages
        msg = InternalGiStatus([{"count": 10}], "foo:1")
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [])

    def testHandleNewConnection(self):
        """Handling of InternalGiStatus when a new client (connWs2)
        connects when (connWs1) is already connected"""
        self.plugin.giStatusByPath["foo:1"] = [True]

        self.plugin.conns.addConn(self.connWs1)

        # Process InternalGiStatus with two clients connected
        msg = InternalConnectWsToGi(self.connWs2)
        self.plugin.processMsg(msg)
        self.assertGiTxQueueMsgs(self.txq, [ClientTxMsg(["GAME-STATUS", "foo:1", True],
                                                        {self.connWs2}, initiatorWs=None)])
