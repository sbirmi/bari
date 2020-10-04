import asyncio
import random
import unittest

from test.MsgTestLib import MsgTestLib
from Dirty7 import (
        Card,
        Dirty7Game,
        Dirty7Room,
        Dirty7Round,
        Exceptions,
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

        roundNum = 1
        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, 7, 40, 100)
        roundParameters = hostParameters.roundParameters(roundNum)

        playerFoo = Dirty7Game.Player(txq, "foo", "1")
        playerFoo.playerConns.addConn(1)
        playerBar = Dirty7Game.Player(txq, "bar", "2")
        playerBar.playerConns.addConn(2)

        playerByName = {playerFoo.name: playerFoo, playerBar.name: playerBar}
        turn = Dirty7Round.Turn(conns, roundNum, list(playerByName), 0)
        #playerByWs = {1: playerByName["foo"],
        #              2: playerByName["bar"]}
        # pylint: disable=unused-variable
        round_ = Dirty7Round.Round("dirty7:1", conns, roundParameters,
                                   playerByName, turn)

        # pylint: disable=bad-continuation
        self.assertGiTxQueueMsgs(txq,
            [ClientTxMsg(["TURN-ORDER", 1, ['foo', 'bar']], {1, 2}),
             ClientTxMsg(["TURN", 1, 'foo'], {1, 2}),
             ClientTxMsg(["ROUND-SCORE", 1, {"foo": None, "bar": None}], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "foo", 7], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "bar", 7], {1, 2}),
             ClientTxMsg(["TABLE-CARDS", 1, 90, 0, [["H", 3]]], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "foo", 7, [['C', 6], ['H', 13], ['D', 12],
                                                        ['C', 3], ['C', 9], ['S', 4],
                                                        ['S', 3]]], {1}),
             ClientTxMsg(["PLAYER-CARDS", 1, "bar", 7, [['S', 13], ['D', 2], ['C', 3],
                                                        ['S', 8], ['C', 13], ['H', 7],
                                                        ['C', 4]]], {2}),
            ], anyOrder=True)

    def testDirty7Room(self):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, 7, 40, 100)
        room = Dirty7Room.Dirty7Room("dirty7:1", "Dirty7 #1", hostParameters)

        ws1 = 1
        ws2 = 2

        room.setRxTxQueues(rxq, txq)
        for msg in (InternalConnectWsToGi(ws1),
                    InternalConnectWsToGi(ws2),
                    ClientRxMsg(["JOIN", "plyr1", "1"], initiatorWs=ws1),
                    ClientRxMsg(["JOIN", "plyr2", "2"], initiatorWs=ws2),
                    ClientRxMsg(["PLAY", {"dropCards": [['H', 3]]}], initiatorWs=ws1),
                    ClientRxMsg(["PLAY", {"dropCards": [['H', 3], ['H', 3]],
                                          "numDrawCards": 0,
                                          "pickCards": [["H", 2], ["S", 4]]}],
                                initiatorWs=ws2),
                    ClientRxMsg(["PLAY", {"dropCards": [['H', 3]],
                                          "numDrawCards": 1,
                                          "pickCards": []}],
                                initiatorWs=ws2),
                   ):
            room.processMsg(msg)

        while not txq.empty():
            print(str(txq.get_nowait()))

    def testDirty7RoomConnectThenJoin(self):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, 7, 40, 100)
        room = Dirty7Room.Dirty7Room("dirty7:1", "Dirty7 #1", hostParameters)

        ws1 = 1
        ws2 = 2

        room.setRxTxQueues(rxq, txq)
        for msg in (InternalConnectWsToGi(ws1),
                    ClientRxMsg(["JOIN", "plyr1", "1"], initiatorWs=ws1),
                    InternalConnectWsToGi(ws2),
                    ClientRxMsg(["JOIN", "plyr2", "2"], initiatorWs=ws2),
                   ):
            room.processMsg(msg)

        self.assertGiTxQueueMsgs(txq, [InternalGiStatus([{'gameState': 1}, 0, hostParameters.state],
                                                        "dirty7:1"),
                                       ClientTxMsg(["JOIN-OKAY"], {1}, initiatorWs=1),
                                       InternalGiStatus([{'gameState': 1}, 0, hostParameters.state],
                                                        "dirty7:1"),
                                       InternalGiStatus([{'gameState': 1}, 0, hostParameters.state],
                                                        "dirty7:1"),
                                       ClientTxMsg(['JOIN-OKAY'], {2}, initiatorWs=2),
                                       ClientTxMsg(['TURN-ORDER', 1, ['plyr2', 'plyr1']], {1, 2}),
                                       ClientTxMsg(['TURN', 1, 'plyr2'], {1, 2}),
                                       ClientTxMsg(['ROUND-SCORE', 1,
                                                    {'plyr1': None, 'plyr2': None}],
                                                   {1, 2}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7], {1, 2}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                                    [['C', 9], ['S', 4], ['S', 3], ['D', 12],
                                                     ['D', 2], ['C', 3], ['S', 8]]], {1}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7], {1, 2}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7,
                                                    [['C', 13], ['H', 7], ['C', 4], ['H', 3],
                                                     ['S', 1], ['D', 13], ['S', 1]]], {2}),
                                       ClientTxMsg(['TABLE-CARDS', 1, 90, 0, [['D', 7]]], {1, 2}),
                                       InternalGiStatus([{'gameState': 4}, 0, hostParameters.state],
                                                        "dirty7:1"),
                                      ])

class PlayerHandTest(unittest.TestCase, MsgTestLib):
    def testContains(self):
        txq = asyncio.Queue()
        conns = Connections(txq)
        playerConns = Connections(txq)
        hand = Dirty7Round.PlayerHand(conns, playerConns, 1, "foo",
                                      [Card.Card(Card.HEARTS, 1),
                                       Card.Card(Card.HEARTS, 1),
                                       Card.Card(Card.CLUBS, 2)])

        self.assertFalse(hand.contains([Card.Card(Card.HEARTS, 2)]))
        self.assertTrue(hand.contains([Card.Card(Card.HEARTS, 1)]))
        self.assertTrue(hand.contains([Card.Card(Card.HEARTS, 1),
                                       Card.Card(Card.HEARTS, 1)]))
        self.assertFalse(hand.contains([Card.Card(Card.HEARTS, 1),
                                        Card.Card(Card.HEARTS, 1),
                                        Card.Card(Card.HEARTS, 1)]))
        self.assertTrue(hand.contains([Card.Card(Card.CLUBS, 2),
                                       Card.Card(Card.HEARTS, 1),
                                       Card.Card(Card.HEARTS, 1)]))
        self.assertFalse(hand.contains([Card.Card(Card.CLUBS, 2),
                                        Card.Card(Card.CLUBS, 2),
                                        Card.Card(Card.HEARTS, 1),
                                        Card.Card(Card.HEARTS, 1)]))

def testTrace():
    class Test2:
        def run(self):
            trace(Level.error, "foo", "bar")

    Test2().run()
    trace(Level.warn, "foo", "bar")
    trace(Level.game, "foo", "bar")
    trace(Level.rnd, "foo", "bar")
    trace(Level.play, "foo", "bar")
    trace(Level.info, "foo", "bar")
    trace(Level.debug, "foo", "bar")
testTrace()
