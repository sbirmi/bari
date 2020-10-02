import asyncio
import random
import unittest

from test.MsgTestLib import MsgTestLib
from Dirty7 import (
        Dirty7Game,
        Dirty7Round,
)
from fwk.MsgSrc import Connections
from fwk.Msg import (
        ClientRxMsg,
        ClientTxMsg,
        InternalConnectWsToGi,
        InternalHost,
        InternalGiStatus,
)
from fwk.Trace import trace, Level

class Dirty7RoomTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        random.seed(1)

    def test1(self):
        rp = Dirty7Round.RoundParameters({"basic"}, 2, 1, 0,
                                         7, 7, 40, 100)
        print(rp.state.numPlayers)

    def testNewGame(self):
        txq = asyncio.Queue()
        conns = Connections(txq)
        conns.addConn(1)
        conns.addConn(2)

        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, 7, 40, 100)
        roundParameters = hostParameters.roundParameters(1)

        playerFoo = Dirty7Game.Player(txq, "foo", "1")
        playerFoo.playerConns.addConn(1)
        playerBar = Dirty7Game.Player(txq, "bar", "2")
        playerBar.playerConns.addConn(2)

        playerByName = {playerFoo.name: playerFoo, playerBar.name: playerBar}
        playerByWs = {1: playerByName["foo"],
                      2: playerByName["bar"]}
        # pylint: disable=unused-variable
        round_ = Dirty7Round.Round("dirty7:1", conns, roundParameters,
                                   playerByName, playerByWs)

        # pylint: disable=bad-continuation
        self.assertGiTxQueueMsgs(txq,
            [ClientTxMsg(["TURN-ORDER", 1, ['bar', 'foo']], {1, 2}),
             ClientTxMsg(["TURN", 1, 'bar'], {1, 2}),
             ClientTxMsg(["ROUND-SCORE", 1, {"foo": None, "bar": None}], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "foo", 7], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "bar", 7], {1, 2}),
             ClientTxMsg(["TABLE-CARDS", 1, 90, 0, [["D", 7]]], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "foo", 7, [['C', 9], ['S', 4], ['S', 3],
                                                        ['D', 12], ['D', 2], ['C', 3],
                                                        ['S', 8]]], {1}),
             ClientTxMsg(["PLAYER-CARDS", 1, "bar", 7, [['C', 13], ['H', 7], ['C', 4],
                                                        ['H', 3], ['S', 1], ['D', 13],
                                                        ['S', 1]]], {2}),
            ], anyOrder=True)

def testTrace():
    class Test2:
        def run(self):
            trace(Level.err, "foo", "bar")

    Test2().run()
    trace(Level.warn, "foo", "bar")
    trace(Level.game, "foo", "bar")
    trace(Level.rnd, "foo", "bar")
    trace(Level.turn, "foo", "bar")
    trace(Level.info, "foo", "bar")
    trace(Level.debug, "foo", "bar")
testTrace()
