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
from fwk.Common import Map
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

    def setUpDirty7Room(self, stopPoints=100):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, [7], 40,
                                                     stopPoints=stopPoints)
        room = Dirty7Room.Dirty7Room("dirty7:1", "Dirty7 #1", hostParameters)

        ws1 = 1
        ws2 = 2

        room.setRxTxQueues(rxq, txq)
        for msg in (InternalConnectWsToGi(ws1),
                    InternalConnectWsToGi(ws2),
                    ClientRxMsg(["JOIN", "plyr1", "1"], initiatorWs=ws1),
                    ClientRxMsg(["JOIN", "plyr2", "2"], initiatorWs=ws2),
                   ):
            room.processMsg(msg)

        return Map(hostParameters=hostParameters, room=room, txq=txq, ws1=ws1, ws2=ws2)

    def testRoundParametersGetAttr(self):
        rp = Dirty7Round.RoundParameters({"basic"}, 2, 1, 0,
                                         7, [7], 40, 100)
        self.assertIs(rp.numPlayers, 2)

    def testNewGame(self):
        txq = asyncio.Queue()
        conns = Connections(txq)
        conns.addConn(1)
        conns.addConn(2)

        roundNum = 1
        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, [7], 40, 100)
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

        self.assertGiTxQueueMsgs(txq,
            [ClientTxMsg(["TURN-ORDER", 1, ['foo', 'bar']], {1, 2}),
             ClientTxMsg(["TURN", 1, 'foo'], {1, 2}),
             ClientTxMsg(["ROUND-SCORE", 1, {"foo": None, "bar": None}], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "foo", 7], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "bar", 7], {1, 2}),
             ClientTxMsg(["TABLE-CARDS", 1, 90, 0, [["D", 7]]], {1, 2}),
             ClientTxMsg(["PLAYER-CARDS", 1, "foo", 7,
                         [['C', 9], ['S', 4], ['S', 3], ['D', 12], ['D', 2], ['C', 3], ['S', 8]]],
                         {1}),
             ClientTxMsg(["PLAYER-CARDS", 1, "bar", 7,
                         [['C', 13], ['H', 7], ['C', 4], ['H', 3], ['S', 1], ['D', 13], ['S', 1]]],
                         {2}),
             ClientTxMsg(['ROUND-PARAMETERS', 1,
                          {'ruleNames': ['basic'],
                           'numPlayers': 2,
                           'numDecks': 2,
                           'numJokers': 1,
                           'numCardsToStart': 7,
                           'declareMaxPoints': [7],
                           'penaltyPoints': 40,
                           'stopPoints': 100}],
                          {1, 2}),
            ], anyOrder=True)

    def testDirty7RoomGameOver(self):
        env = self.setUpDirty7Room(stopPoints=30)
        self.drainGiTxQueue(env.txq)
        turnPlayerName = env.room.rounds[-1].turn.playerNameInTurnOrder[0]
        turnWs = env.ws1 if turnPlayerName == "plyr1" else env.ws2
        prs = env.room.rounds[-1].playerRoundStatus[turnPlayerName]

        # Declare with 7 points
        prs.hand.setCards([Card.Card(Card.SPADES, 7)])
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                                        [['S', 7]]],
                                                       {env.ws2}),
                                          ], anyOrder=True)
        env.room.processMsg(ClientRxMsg(["DECLARE"], initiatorWs=turnWs))
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                                        [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                         ['C', 3], ['S', 8], ['C', 13]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                                        [['S', 7]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['UPDATE', 1, {'DECLARE': ['plyr2', 7]}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-SCORE', 1,
                                                        {'plyr1': 40, 'plyr2': 0}],
                                                       {env.ws1, env.ws2}),
                                           InternalGiStatus([{'gameState': 'GameOver',
                                                              'clientCount': {'plyr1': 1,
                                                                              'plyr2': 1},
                                                              'spectatorCount': 0},
                                                             0, env.hostParameters.state,
                                                             1, env.hostParameters.state],
                                                            "dirty7:1"),
                                           ClientTxMsg(['GAME-OVER', ['plyr2']],
                                                       {env.ws1, env.ws2}),
                                          ], anyOrder=True)

        # Add a new player (as spectator) and see what messages are created
        ws10 = 10
        env.room.processMsg(InternalConnectWsToGi(ws10))
        self.assertGiTxQueueMsgs(env.txq,
                                 [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                               [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                ['C', 3], ['S', 8], ['C', 13]]],
                                              {ws10}),
                                  ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                               [['S', 7]]],
                                              {ws10}),
                                  ClientTxMsg(['ROUND-SCORE', 1, {'plyr1': 40, 'plyr2': 0}],
                                              {ws10}),
                                  InternalGiStatus([{'gameState': 'GameOver',
                                                     'clientCount': {'plyr1': 1,
                                                                     'plyr2': 1},
                                                     'spectatorCount': 1},
                                                    0, env.hostParameters.state,
                                                    1, env.hostParameters.state],
                                                   "dirty7:1"),
                                  ClientTxMsg(['GAME-OVER', ['plyr2']], {ws10}),
                                  ClientTxMsg(['ROUND-PARAMETERS', 1,
                                               {'ruleNames': ['basic'],
                                                'numPlayers': 2,
                                                'numDecks': 2,
                                                'numJokers': 1,
                                                'numCardsToStart': 7,
                                                'declareMaxPoints': [7],
                                                'penaltyPoints': 40,
                                                'stopPoints': 30}],
                                               {ws10}),
                                 ], anyOrder=True)

        # Have the spectator join and see what messages are created
        env.room.processMsg(ClientRxMsg(["JOIN", "plyr1", "1"], initiatorWs=ws10))
        self.assertGiTxQueueMsgs(env.txq,
                                 [ClientTxMsg(['JOIN-BAD', 'Game over already'],
                                              {ws10}, initiatorWs=ws10),
                                 ])

    def testDirty7RoomBasicDeclare(self):
        env = self.setUpDirty7Room()
        self.drainGiTxQueue(env.txq)

        turnPlayerName = env.room.rounds[-1].turn.playerNameInTurnOrder[0]
        turnWs = env.ws1 if turnPlayerName == "plyr1" else env.ws2
        prs = env.room.rounds[-1].playerRoundStatus[turnPlayerName]

        # Declare with 8 points
        prs.hand.setCards([Card.Card(Card.SPADES, 8)])
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                                        [['S', 8]]],
                                                       {env.ws2}),
                                          ])
        env.room.processMsg(ClientRxMsg(["DECLARE"], initiatorWs=turnWs))
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['DECLARE-BAD', 'Invalid declare'],
                                                       {env.ws2}, initiatorWs=turnWs),
                                          ])

        # Declare with 7 points
        prs.hand.setCards([Card.Card(Card.SPADES, 7)])
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                                        [['S', 7]]],
                                                       {env.ws2}),
                                          ], anyOrder=True)
        env.room.processMsg(ClientRxMsg(["DECLARE"], initiatorWs=turnWs))
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                                        [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                         ['C', 3], ['S', 8], ['C', 13]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                                        [['S', 7]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['UPDATE', 1, {'DECLARE': ['plyr2', 7]}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-SCORE', 1,
                                                        {'plyr1': 40, 'plyr2': 0}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['TURN-ORDER', 2, ['plyr2', 'plyr1']],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['TURN', 2, 'plyr1'],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-SCORE', 2,
                                                        {'plyr1': None, 'plyr2': None}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr1', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr1', 7,
                                                        [['D', 6], ['D', 12], ['H', 2], ['H', 9],
                                                         ['C', 9], ['H', 5], ['D', 7]]],
                                                       {env.ws1}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr2', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr2', 7,
                                                        [['D', 11], ['C', 1], ['D', 13], ['H', 11],
                                                         ['D', 4], ['C', 5], ['H', 4]]],
                                                       {env.ws2}),
                                           ClientTxMsg(['TABLE-CARDS', 2, 90, 0, [['S', 5]]],
                                                       {env.ws1, env.ws2}),
                                           InternalGiStatus([{'gameState': 'PlayerTurn',
                                                              'clientCount': {'plyr1': 1,
                                                                              'plyr2': 1},
                                                              'spectatorCount': 0},
                                                             0, env.hostParameters.state,
                                                             2, env.hostParameters.state],
                                                            "dirty7:1"),
                                           ClientTxMsg(['ROUND-PARAMETERS', 2,
                                                        {'ruleNames': ['basic'],
                                                         'numPlayers': 2,
                                                         'numDecks': 2,
                                                         'numJokers': 1,
                                                         'numCardsToStart': 7,
                                                         'declareMaxPoints': [7],
                                                         'penaltyPoints': 40,
                                                         'stopPoints': 100}],
                                                        {env.ws1, env.ws2}),
                                          ], anyOrder=True)

        # Add a new player (as spectator) and see what messages are created
        ws10 = 10
        env.room.processMsg(InternalConnectWsToGi(ws10))
        self.assertGiTxQueueMsgs(env.txq,
                                 [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                               [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                ['C', 3], ['S', 8], ['C', 13]]],
                                              {ws10}),
                                  ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                               [['S', 7]]],
                                              {ws10}),
                                  ClientTxMsg(['ROUND-SCORE', 1, {'plyr1': 40, 'plyr2': 0}],
                                              {ws10}),
                                  ClientTxMsg(['TURN-ORDER', 2, ['plyr2', 'plyr1']],
                                              {ws10}),
                                  ClientTxMsg(['TURN', 2, 'plyr1'],
                                              {ws10}),
                                  ClientTxMsg(['PLAYER-CARDS', 2, 'plyr1', 7],
                                              {ws10}),
                                  ClientTxMsg(['PLAYER-CARDS', 2, 'plyr2', 7],
                                              {ws10}),
                                  ClientTxMsg(['TABLE-CARDS', 2, 90, 0, [['S', 5]]],
                                              {ws10}),
                                  ClientTxMsg(['ROUND-SCORE', 2, {'plyr1': None, 'plyr2': None}],
                                              {ws10}),
                                  InternalGiStatus([{'gameState': 'PlayerTurn',
                                                     'clientCount': {'plyr1': 1,
                                                                     'plyr2': 1},
                                                     'spectatorCount': 1},
                                                    0, env.hostParameters.state,
                                                    2, env.hostParameters.state],
                                                   "dirty7:1"),
                                  ClientTxMsg(['ROUND-PARAMETERS', 1,
                                               {'ruleNames': ['basic'],
                                                'numPlayers': 2,
                                                'numDecks': 2,
                                                'numJokers': 1,
                                                'numCardsToStart': 7,
                                                'declareMaxPoints': [7],
                                                'penaltyPoints': 40,
                                                'stopPoints': 100}],
                                               {ws10}),
                                  ClientTxMsg(['ROUND-PARAMETERS', 2,
                                               {'ruleNames': ['basic'],
                                                'numPlayers': 2,
                                                'numDecks': 2,
                                                'numJokers': 1,
                                                'numCardsToStart': 7,
                                                'declareMaxPoints': [7],
                                                'penaltyPoints': 40,
                                                'stopPoints': 100}],
                                               {ws10}),
                                 ], anyOrder=True)

        # Have the spectator join and see what messages are created
        env.room.processMsg(ClientRxMsg(["JOIN", "plyr1", "1"], initiatorWs=ws10))
        self.assertGiTxQueueMsgs(env.txq,
                                 [ClientTxMsg(['JOIN-OKAY'],
                                              {ws10}, initiatorWs=ws10),
                                  ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                               [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                ['C', 3], ['S', 8], ['C', 13]]],
                                              {ws10}),
                                  ClientTxMsg(['PLAYER-CARDS', 2, 'plyr1', 7,
                                               [['D', 6], ['D', 12], ['H', 2], ['H', 9],
                                                ['C', 9], ['H', 5], ['D', 7]]],
                                              {ws10}),
                                 ], anyOrder=True)

    def testDirty7RoomDeclareGetsPenalty(self):
        env = self.setUpDirty7Room()
        self.drainGiTxQueue(env.txq)

        turnPlayerName = env.room.rounds[-1].turn.playerNameInTurnOrder[0]
        otherPlayerName = env.room.rounds[-1].turn.playerNameInTurnOrder[1]
        turnWs = env.ws1 if turnPlayerName == "plyr1" else env.ws2
        turnPrs = env.room.rounds[-1].playerRoundStatus[turnPlayerName]
        otherPrs = env.room.rounds[-1].playerRoundStatus[otherPlayerName]

        # Initial cards
        turnPrs.hand.setCards([Card.Card(Card.SPADES, 4)])
        otherPrs.hand.setCards([Card.Card(Card.SPADES, 2)])

        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1,
                                                        [['S', 4]]],
                                                       {env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 1],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 1,
                                                        [['S', 2]]],
                                                       {env.ws1}),
                                          ])
        env.room.processMsg(ClientRxMsg(["DECLARE"], initiatorWs=turnWs))
        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['UPDATE', 1, {'DECLARE': ['plyr2', 4]}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-SCORE', 1, {'plyr1': 0,
                                                                           'plyr2': 40}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 1, [['S', 2]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 1, [['S', 4]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['TURN-ORDER', 2, ['plyr2', 'plyr1']],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['TURN', 2, 'plyr1'],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-SCORE', 2, {'plyr1': None,
                                                                           'plyr2': None}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr1', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr1', 7,
                                                        [['D', 6], ['D', 12], ['H', 2], ['H', 9],
                                                         ['C', 9], ['H', 5], ['D', 7]]],
                                                       {env.ws1}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr2', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 2, 'plyr2', 7,
                                                        [['D', 11], ['C', 1], ['D', 13], ['H', 11],
                                                         ['D', 4], ['C', 5], ['H', 4]]],
                                                       {env.ws2}),
                                           ClientTxMsg(['TABLE-CARDS', 2, 90, 0, [['S', 5]]],
                                                       {env.ws1, env.ws2}),
                                           InternalGiStatus([{'gameState': 'PlayerTurn',
                                                              'clientCount': {'plyr1': 1,
                                                                              'plyr2': 1},
                                                              'spectatorCount': 0},
                                                              0, env.hostParameters.state,
                                                              2, env.hostParameters.state,
                                                            ], "dirty7:1"),
                                           ClientTxMsg(['ROUND-PARAMETERS', 2,
                                                        {'ruleNames': ['basic'],
                                                         'numPlayers': 2,
                                                         'numDecks': 2,
                                                         'numJokers': 1,
                                                         'numCardsToStart': 7,
                                                         'declareMaxPoints': [7],
                                                         'penaltyPoints': 40,
                                                         'stopPoints': 100}],
                                                        {env.ws1, env.ws2}),
                                          ], anyOrder=True)

    def testDirty7RoomBadMoves(self):
        env = self.setUpDirty7Room()
        self.drainGiTxQueue(env.txq)

        for msg in (ClientRxMsg(["PLAY", {"dropCards": [['H', 3]]}], initiatorWs=env.ws1),
                    ClientRxMsg(["PLAY", {"dropCards": [['H', 3], ['H', 3]],
                                          "numDrawCards": 0,
                                          "pickCards": [["H", 2], ["S", 4]]}],
                                initiatorWs=env.ws2),
                    ClientRxMsg(["DECLARE"], initiatorWs=env.ws1),
                    ClientRxMsg(["DECLARE"], initiatorWs=env.ws2),
                   ):
            env.room.processMsg(msg)

        self.assertGiTxQueueMsgs(env.txq, [ClientTxMsg(['PLAY-BAD', 'It is not your turn'],
                                                       {env.ws1}, initiatorWs=env.ws1),
                                           ClientTxMsg(['PLAY-BAD', 'Picking cards not available',
                                                        [['H', 2], ['S', 4]]],
                                                       {env.ws2}, initiatorWs=env.ws2),
                                           ClientTxMsg(['DECLARE-BAD', 'It is not your turn'],
                                                       {env.ws1}, initiatorWs=env.ws1),
                                           ClientTxMsg(['DECLARE-BAD', 'Invalid declare'],
                                                       {env.ws2}, initiatorWs=env.ws2),
                                          ])

    def testDirty7Room(self):
        env = self.setUpDirty7Room()
        for msg in (ClientRxMsg(["PLAY", {"dropCards": [['H', 3]],
                                          "numDrawCards": 1,
                                          "pickCards": []}],
                                initiatorWs=env.ws2),
                   ):
            env.room.processMsg(msg)

        self.assertGiTxQueueMsgs(env.txq, [InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                              'clientCount': {},
                                                              'spectatorCount': 0},
                                                             0, env.hostParameters.state],
                                                            "dirty7:1"),
                                           InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                              'clientCount': {},
                                                              'spectatorCount': 1},
                                                             0, env.hostParameters.state],
                                                            "dirty7:1"),
                                           InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                              'clientCount': {},
                                                              'spectatorCount': 2},
                                                             0, env.hostParameters.state],
                                                            "dirty7:1"),
                                           ClientTxMsg(["JOIN-OKAY"], {env.ws1},
                                                       initiatorWs=env.ws1),
                                           InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                              'clientCount': {'plyr1': 1},
                                                              'spectatorCount': 1},
                                                             0, env.hostParameters.state],
                                                            "dirty7:1"),
                                           ClientTxMsg(["JOIN-OKAY"], {env.ws2},
                                                       initiatorWs=env.ws2),
                                           ClientTxMsg(['TURN-ORDER', 1, ['plyr2', 'plyr1']],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['TURN', 1, 'plyr2'], {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-PARAMETERS', 1,
                                                        {'ruleNames': ['basic'],
                                                         'numPlayers': 2,
                                                         'numDecks': 2,
                                                         'numJokers': 1,
                                                         'numCardsToStart': 7,
                                                         'declareMaxPoints': [7],
                                                         'penaltyPoints': 40,
                                                         'stopPoints': 100}],
                                                        {env.ws1, env.ws2}),
                                           ClientTxMsg(['ROUND-SCORE', 1,
                                                        {'plyr1': None, 'plyr2': None}],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                                        [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                         ['C', 3], ['S', 8], ['C', 13]]],
                                                        {env.ws1}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7,
                                                        [['H', 7], ['C', 4], ['H', 3], ['S', 1],
                                                         ['D', 13], ['S', 1], ['D', 7]]],
                                                       {env.ws2}),
                                           ClientTxMsg(['TABLE-CARDS', 1, 90, 0, [['C', 1]]],
                                                       {env.ws1, env.ws2}),
                                           InternalGiStatus([{'gameState': 'PlayerTurn',
                                                              'clientCount': {'plyr1': 1,
                                                                              'plyr2': 1},
                                                              'spectatorCount': 0},
                                                             0, env.hostParameters.state,
                                                             1, env.hostParameters.state],
                                                            "dirty7:1"),
                                           ClientTxMsg(['TABLE-CARDS', 1, 89, 1, [['H', 3]]],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7],
                                                       {env.ws1, env.ws2}),
                                           ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7,
                                                        [['H', 7], ['C', 4], ['S', 1], ['D', 13],
                                                         ['S', 1], ['D', 7], ['C', 13]]],
                                                       {env.ws2}),
                                           ClientTxMsg(['UPDATE', 1, {'PLAY': ['plyr2', [['H', 3]],
                                                                               1, [],
                                                                               {'AdvanceTurn': 1}]}
                                                       ], {env.ws1, env.ws2}),
                                           ClientTxMsg(['TURN', 1, 'plyr1'], {env.ws1, env.ws2}),
                                          ],
                                          anyOrder=True)

    def testDirty7RoomConnectThenJoin(self):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = Dirty7Round.RoundParameters(["basic"], 2, 2, 1, 7, [7], 40, 100)
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

        self.assertGiTxQueueMsgs(txq, [InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                          'clientCount': {},
                                                          'spectatorCount': 0},
                                                         0, hostParameters.state],
                                                        "dirty7:1"),
                                       InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                          'clientCount': {},
                                                          'spectatorCount': 1},
                                                         0, hostParameters.state],
                                                        "dirty7:1"),
                                       ClientTxMsg(["JOIN-OKAY"], {1}, initiatorWs=1),
                                       InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                          'clientCount': {'plyr1': 1},
                                                          'spectatorCount': 0},
                                                         0, hostParameters.state],
                                                        "dirty7:1"),
                                       InternalGiStatus([{'gameState': 'WaitingForPlayers',
                                                          'clientCount': {'plyr1': 1},
                                                          'spectatorCount': 1},
                                                         0, hostParameters.state],
                                                        "dirty7:1"),
                                       ClientTxMsg(['JOIN-OKAY'], {2}, initiatorWs=2),
                                       ClientTxMsg(['TURN-ORDER', 1, ['plyr2', 'plyr1']], {1, 2}),
                                       ClientTxMsg(['TURN', 1, 'plyr2'], {1, 2}),
                                       ClientTxMsg(['ROUND-SCORE', 1,
                                                    {'plyr1': None, 'plyr2': None}],
                                                   {1, 2}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7], {1, 2}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr1', 7,
                                                    [['S', 4], ['S', 3], ['D', 12], ['D', 2],
                                                     ['C', 3], ['S', 8], ['C', 13]]], {1}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7], {1, 2}),
                                       ClientTxMsg(['PLAYER-CARDS', 1, 'plyr2', 7,
                                                    [['H', 7], ['C', 4], ['H', 3], ['S', 1],
                                                     ['D', 13], ['S', 1], ['D', 7]]], {2}),
                                       ClientTxMsg(['TABLE-CARDS', 1, 90, 0, [['C', 1]]], {1, 2}),
                                       InternalGiStatus([{'gameState': 'PlayerTurn',
                                                          'clientCount': {'plyr1': 1,
                                                                          'plyr2': 1},
                                                          'spectatorCount': 0},
                                                         0, hostParameters.state,
                                                         1, hostParameters.state],
                                                        "dirty7:1"),
                                       ClientTxMsg(['ROUND-PARAMETERS', 1,
                                                    {'ruleNames': ['basic'],
                                                     'numPlayers': 2,
                                                     'numDecks': 2,
                                                     'numJokers': 1,
                                                     'numCardsToStart': 7,
                                                     'declareMaxPoints': [7],
                                                     'penaltyPoints': 40,
                                                     'stopPoints': 100}],
                                                    {1, 2}),
                                      ], anyOrder=True)

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
