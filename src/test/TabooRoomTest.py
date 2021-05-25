import asyncio
from contextlib import contextmanager
import unittest

from test.MsgTestLib import MsgTestLib
from fwk.Common import Map
from fwk.Msg import (
        ClientRxMsg,
        ClientTxMsg,
        InternalGiStatus,
        TimerRequest,
)
from fwk.MsgSrc import Connections
from Taboo import TabooRoom
from Taboo.HostParameters import HostParameters
from Taboo.TabooPlayer import TabooPlayer
from Taboo.TabooTeam import TabooTeam
from Taboo.Word import (
        Word,
        WordState,
)
import Taboo.TurnManager
from Taboo.TurnManager import TurnManager
from Taboo.WordSets import SupportedWordSets

# pylint: disable=protected-access
# pylint: disable=dangerous-default-value
# pylint: disable=too-many-locals

@contextmanager
def stub(obj, attr, tempVal):
    """Stub attribute in object with a temporary value for testing

    Example:

        with stub(obj, "attrName", some-temp-value):
            # do testing
    """
    prevVal = getattr(obj, attr)
    setattr(obj, attr, tempVal)
    yield
    setattr(obj, attr, prevVal)

@contextmanager
def stubs(objAttrTempValList):
    """Stub a list of (obj, attr) with tempVals

    Example

    with stubs([(obj1, attrName1, tempVal1),
                (obj2, attrName2, tempVal2),]):
        # do testing
    """
    _stubs = [stub(*args) for args in objAttrTempValList]
    for _stub in _stubs:
        _stub.__enter__()

    yield

    for _stub in _stubs:
        _stub.__exit__(None, None, None)

def stubExpiryEpochGen():
    def expiryEpoch(offsetSec, counter=[0]):
        ans = counter[0] + offsetSec
        counter[0] = counter[0] + 1
        return ans
    return expiryEpoch

def mockPlyrTeam(txq, allConns, teamId : int,
                 connsByPlayerName,
                 turnsPlayedByPlayerName=None):
    turnsPlayedByPlayerName = turnsPlayedByPlayerName or {}

    team = TabooTeam(txq, Connections(txq), teamId)
    for plyrName, conns in connsByPlayerName.items():
        plyr = TabooPlayer(txq, allConns, name=plyrName, team=team)
        for ws in conns:
            plyr.addConn(ws)
        plyr.turnsPlayed = turnsPlayedByPlayerName.get(plyrName, 0)
    return team

class TabooRoomTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        def mockNextWord(requestor, remainingWords=[ # pylint: disable= unused-argument
                            Map(word="c", disallowed=["c1", "c2"]),
                            Map(word="a", disallowed=["a1", "a2"]),
                            Map(word="b", disallowed=["b1", "b2"]),
                         ]):
            if remainingWords:
                return remainingWords.pop(0)
            return None
        self.mockNextWord = mockNextWord

    def setUpTabooRoom(self):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=1)
        room = TabooRoom.TabooRoom("taboo:1", "Taboo Room #1", hostParameters)
        room.setRxTxQueues(rxq, txq)

        return Map(rxq=rxq,
                   txq=txq,
                   hostParameters=hostParameters,
                   room=room)

    def setUpTeamPlayer(self, env, teamId, plyrName, wss):
        for ws in wss:
            env.room.joinPlayer(ws, plyrName, teamId)
            assert ws in env.room.teams[teamId].conns._wss
            env.room.conns.addConn(ws)

    def testNewGame(self):
        env = self.setUpTabooRoom()

        self.assertGiTxQueueMsgs(env.txq, [
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": {1: {}, 2: {}},
                 "winners": []}
            ], "taboo:1"),
        ], anyOrder=True)

        ws1 = 1
        env.room.processConnect(ws1)

        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["TEAM-STATUS", 1, []], {ws1}),
            ClientTxMsg(["TEAM-STATUS", 2, []], {ws1}),
            ClientTxMsg(['HOST-PARAMETERS', {'numTeams': 2,
                                             'turnDurationSec': 30,
                                             'wordSets': ['test'],
                                             'numTurns': 1}], {ws1}),
            ClientTxMsg(["SCORE", {1: 0, 2: 0}],
                        {ws1}),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": {1: {}, 2: {}},
                 "winners":[]
                }
            ], "taboo:1"),
        ], anyOrder=True)

    def testJoin(self):
        env = self.setUpTabooRoom()
        ws1 = 101
        env.room.processConnect(ws1)
        self.drainGiTxQueue(env.txq)

        env.room.processMsg(ClientRxMsg(["JOIN"], ws1))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["JOIN-BAD", "Invalid message length"], {ws1}, ws1),
        ])

        env.room.processMsg(ClientRxMsg(["JOIN", "sb1", -1], ws1))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["JOIN-BAD", "Invalid team number", -1], {ws1}, ws1),
        ])

        env.room.processMsg(ClientRxMsg(["JOIN", "sb1", 3], ws1))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["JOIN-BAD", "Invalid team number", 3], {ws1}, ws1),
        ])

        env.room.processMsg(ClientRxMsg(["JOIN", "#$H", 1], ws1))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["JOIN-BAD", "Invalid player name", "#$H"], {ws1}, ws1),
        ])

        #Good join - specified team number
        env.room.processMsg(ClientRxMsg(["JOIN", "sb1", 1], ws1))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(['PLAYER-STATUS', 'sb1', {'numConns': 0, 'ready': False, 'turnsPlayed': 0}],
                        {101}),
            ClientTxMsg(['PLAYER-STATUS', 'sb1', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {101}),
            ClientTxMsg(["TEAM-STATUS", 1, ["sb1"]], {101}),
            ClientTxMsg(["JOIN-OKAY", "sb1", 1], {ws1}, ws1),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": {1: {'sb1': 1}, 2: {}},
                 "winners": []
                }
            ], "taboo:1"),
        ], anyOrder=True)

        #Join more players
        self.setUpTeamPlayer(env, 1, "sb2", [102])
        self.setUpTeamPlayer(env, 2, "jg1", [201])
        self.setUpTeamPlayer(env, 2, "jg2", [202])
        #Join one more player in team 2
        self.setUpTeamPlayer(env, 2, "jg3", [203])
        self.drainGiTxQueue(env.txq)

        #A random-team join (team = 0) should lead to "water-fill"
        ws2 = 1001
        env.room.processConnect(ws2)
        self.drainGiTxQueue(env.txq)
        env.room.processMsg(ClientRxMsg(["JOIN", "xx", 0], ws2))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["TEAM-STATUS", 1, ["sb1", "sb2", "xx"]],
                        {101, 102, 201, 202, 203, 1001}),
            ClientTxMsg(['PLAYER-STATUS', 'xx', {'numConns': 0, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001}),
            ClientTxMsg(['PLAYER-STATUS', 'xx', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001}),
            ClientTxMsg(["JOIN-OKAY", "xx", 1], {ws2}, ws2),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": {1: {'sb1': 1, 'sb2': 1, 'xx': 1},
                                 2: {'jg1': 1, 'jg2': 1, 'jg3': 1}},
                 "winners": []
                }
            ], "taboo:1"),
        ], anyOrder=True)

        #Now run a bunch of new JOINs on team 2
        self.setUpTeamPlayer(env, 2, "jg4", [204])
        self.setUpTeamPlayer(env, 2, "jg5", [205])

        # The next two random JOINs should be assgnd team 1
        ws2 = ws2 + 1
        env.room.processConnect(ws2)
        self.drainGiTxQueue(env.txq)
        env.room.processMsg(ClientRxMsg(["JOIN", "yy", 0], ws2))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["TEAM-STATUS", 1, ["sb1", "sb2", "xx", "yy"]],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002}),
            ClientTxMsg(['PLAYER-STATUS', 'yy', {'numConns': 0, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002}),
            ClientTxMsg(['PLAYER-STATUS', 'yy', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002}),
            ClientTxMsg(["JOIN-OKAY", "yy", 1], {ws2}, ws2),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": {1: {'sb1': 1, 'sb2': 1, 'xx': 1, 'yy': 1},
                     2: {'jg1': 1, 'jg2': 1, 'jg3': 1, 'jg4': 1, 'jg5': 1}},
                 "winners": []
                }
            ], "taboo:1"),
        ], anyOrder=True)

        ws2 = ws2 + 1
        env.room.processConnect(ws2)
        self.drainGiTxQueue(env.txq)
        env.room.processMsg(ClientRxMsg(["JOIN", "zz", 0], ws2))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["TEAM-STATUS", 1, ["sb1", "sb2", "xx", "yy", "zz"]],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002, 1003}),
            ClientTxMsg(['PLAYER-STATUS', 'zz', {'numConns': 0, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002, 1003}),
            ClientTxMsg(['PLAYER-STATUS', 'zz', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002, 1003}),
            ClientTxMsg(["JOIN-OKAY", "zz", 1], {ws2}, ws2),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": {1: {'sb1': 1, 'sb2': 1, 'xx': 1, 'yy': 1, 'zz': 1},
                     2: {'jg1': 1, 'jg2': 1, 'jg3': 1, 'jg4': 1, 'jg5': 1}},
                 "winners": []
                }
            ], "taboo:1"),
        ], anyOrder=True)

        #A JOIN from an unrecognized ws ofc leads to assert
        with self.assertRaises(AssertionError):
            env.room.processMsg(ClientRxMsg(["JOIN", "zz", 0], ws2+1))

        #A re-JOIN from a plyr forces it to its original team
        env.room.processConnect(2001)
        self.drainGiTxQueue(env.txq)
        env.room.processMsg(ClientRxMsg(["JOIN", "jg1", 1], 2001))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(['PLAYER-STATUS', 'jg1', {'numConns': 2, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002, 1003, 2001}),
            ClientTxMsg(["JOIN-OKAY", "jg1", 2], {2001}, 2001),
            InternalGiStatus([
                {'hostParameters': {'numTeams': 2,
                                    'turnDurationSec': 30,
                                    'wordSets': ['test'],
                                    'numTurns': 1},
                 'gameState': 'WAITING_TO_START',
                 'clientCount': {1: {'sb1': 1, 'sb2': 1, 'xx': 1, 'yy': 1, 'zz': 1},
                                 2: {'jg1': 2, 'jg2': 1, 'jg3': 1, 'jg4': 1, 'jg5': 1}},
                 'winners': []
                }
            ], "taboo:1"),
        ], anyOrder=True)

        #A re-JOIN from a plyr forces it to its original team
        env.room.processConnect(2002)
        self.drainGiTxQueue(env.txq)
        env.room.processMsg(ClientRxMsg(["JOIN", "jg1", 0], 2002))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(['PLAYER-STATUS', 'jg1', {'numConns': 3, 'ready': False, 'turnsPlayed': 0}],
                        {101, 102, 201, 202, 203, 1001, 204, 205, 1002, 1003, 2001, 2002}),
            ClientTxMsg(["JOIN-OKAY", "jg1", 2], {2002}, 2002),
            InternalGiStatus([
                {'hostParameters': {'numTeams': 2,
                                    'turnDurationSec': 30,
                                    'wordSets': ['test'],
                                    'numTurns': 1},
                 'gameState': 'WAITING_TO_START',
                 'clientCount': {1: {'sb1': 1, 'sb2': 1, 'xx': 1, 'yy': 1, 'zz': 1},
                                 2: {'jg1': 3, 'jg2': 1, 'jg3': 1, 'jg4': 1, 'jg5': 1}},
                 'winners': []
                }
            ], "taboo:1"),
        ], anyOrder=True)

    def testKickoff(self):
        env = self.setUpTabooRoom()
        self.drainGiTxQueue(env.txq)

        with stubs([(SupportedWordSets["test"], "nextWord", self.mockNextWord),
                    (Taboo.TurnManager, "expiryEpoch", stubExpiryEpochGen())]):
            env.room.processMsg(ClientRxMsg(["KICKOFF", 2], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["KICKOFF-BAD", "Invalid message length"], {101}, 101),
            ])

            env.room.processMsg(ClientRxMsg(["KICKOFF"], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["KICKOFF-BAD", "Game not running"], {101}, 101),
            ])

            env.room.state = TabooRoom.GameState.RUNNING
            self.setUpTeamPlayer(env, 1, "sb1", [101])
            self.setUpTeamPlayer(env, 1, "sb2", [102])
            self.setUpTeamPlayer(env, 2, "jg1", [201])
            self.setUpTeamPlayer(env, 2, "jg2", [202])
            self.drainGiTxQueue(env.txq)

            env.room.processMsg(ClientRxMsg(["KICKOFF"], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["KICKOFF-BAD", "It is not your turn"], {101}, 101),
            ])

            def mockFindNextPlayer(remainingPlayers=[
                    env.room.playerByWs[201],
                    env.room.playerByWs[101],
                    env.room.playerByWs[202],
                ]):
                if remainingPlayers:
                    return remainingPlayers.pop(0)
                return None
            with stub(env.room.turnMgr, "_findNextPlayer", mockFindNextPlayer):
                env.room.turnMgr.startNewTurn()
                env.room.processMsg(ClientRxMsg(["KICKOFF"], 101))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["WAIT-FOR-KICKOFF", 1, "jg1"], {101, 102, 201, 202}, None),
                    ClientTxMsg(["KICKOFF-BAD", "It is not your turn"], {101}, 101),
                ])

                env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
                secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                            'utcTimeout': 30,
                                            'secret': 'c', 'disallowed': ['c1', 'c2']}]
                publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                            'utcTimeout': 30}]
                self.assertGiTxQueueMsgs(env.txq, [
                    TimerRequest(30, env.room.turnMgr.timerExpiredCb, {
                                    "turnId": 1,
                                 }),
                    ClientTxMsg(secretMsg, {201}),
                    ClientTxMsg(secretMsg, {101, 102}),
                    ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                ], anyOrder=True)

                env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["KICKOFF-BAD", "Can't kickoff a turn"], {201}, 201),
                ])

    def testReady(self):
        env = self.setUpTabooRoom()
        self.drainGiTxQueue(env.txq)

        env.room.state = TabooRoom.GameState.WAITING_TO_START

        env.room.processMsg(ClientRxMsg(["READY", "stuff"], 101))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["READY-BAD", "Invalid message length"], {101}, 101),
        ])

        env.room.processMsg(ClientRxMsg(["READY"], 101))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["READY-BAD", "Join first"], {101}, 101),
        ])

        self.setUpTeamPlayer(env, 1, "sb1", [101])
        self.setUpTeamPlayer(env, 1, "sb2", [102])
        self.setUpTeamPlayer(env, 2, "jg1", [201])
        self.setUpTeamPlayer(env, 2, "jg2", [202])
        self.drainGiTxQueue(env.txq)

        def mockFindNextPlayer(remainingPlayers=[
                env.room.playerByWs[201],
                env.room.playerByWs[101],
                env.room.playerByWs[202],
            ]):
            if remainingPlayers:
                return remainingPlayers.pop(0)
            return None
        with stub(env.room.turnMgr, "_findNextPlayer", mockFindNextPlayer):
            env.room.processMsg(ClientRxMsg(["READY"], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(['PLAYER-STATUS', 'sb1', {'numConns': 1,
                                                      'ready': True,
                                                      'turnsPlayed': 0}],
                            {101, 102, 201, 202}),
            ])
            self.assertEqual(env.room.state, TabooRoom.GameState.WAITING_TO_START)
            env.room.processMsg(ClientRxMsg(["READY"], 102))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(['PLAYER-STATUS', 'sb2', {'numConns': 1,
                                                      'ready': True,
                                                      'turnsPlayed': 0}],
                            {101, 102, 201, 202}),
            ])
            self.assertEqual(env.room.state, TabooRoom.GameState.WAITING_TO_START)
            env.room.processMsg(ClientRxMsg(["READY"], 201))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(['PLAYER-STATUS', 'jg1', {'numConns': 1,
                                                      'ready': True,
                                                      'turnsPlayed': 0}],
                            {101, 102, 201, 202}),
            ])
            self.assertEqual(env.room.state, TabooRoom.GameState.WAITING_TO_START)

            #If a player sends READY multiple times, it is replied with a READY-BAD
            env.room.processMsg(ClientRxMsg(["READY"], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(['READY-BAD', 'Already ready'], {101}, 101)
            ])

            #READY from last of the (initial) players trigger start of the game
            env.room.processMsg(ClientRxMsg(["READY"], 202))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(['PLAYER-STATUS', 'jg2', {'numConns': 1,
                                                      'ready': True,
                                                      'turnsPlayed': 0}],
                            {101, 102, 201, 202}),
                ClientTxMsg(["WAIT-FOR-KICKOFF", 1, "jg1"], {101, 102, 201, 202}, None),
            ])
            self.assertEqual(env.room.state, TabooRoom.GameState.RUNNING)

            #A late-joinee is connected in READY state when it joins
            self.setUpTeamPlayer(env, 1, "sb3", [103])
            self.drainGiTxQueue(env.txq)
            env.room.processMsg(ClientRxMsg(["READY"], 103))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(['READY-BAD', 'Already ready'], {103}, 103)
            ])

    def testTurnTimeOut(self):
        env = self.setUpTabooRoom()

        env.room.state = TabooRoom.GameState.RUNNING
        self.setUpTeamPlayer(env, 1, "sb1", [101])
        self.setUpTeamPlayer(env, 1, "sb2", [102])
        self.setUpTeamPlayer(env, 2, "jg1", [201])
        self.setUpTeamPlayer(env, 2, "jg2", [202])
        self.drainGiTxQueue(env.txq)

        def mockFindNextPlayer(remainingPlayers=[
                env.room.playerByWs[201],
                env.room.playerByWs[101],
                env.room.playerByWs[202],
            ]):
            if remainingPlayers:
                return remainingPlayers.pop(0)
            return None
        with stubs([(SupportedWordSets["test"], "nextWord", self.mockNextWord),
                    (Taboo.TurnManager, "expiryEpoch", stubExpiryEpochGen()),
                    (env.room.turnMgr, "_findNextPlayer", mockFindNextPlayer)]):
            env.room.turnMgr.startNewTurn()
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["WAIT-FOR-KICKOFF", 1, "jg1"], {101, 102, 201, 202}, None),
            ], anyOrder=True)

            # Start the timer by issuing a KICKOFF
            env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
            secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                        'utcTimeout': 30,
                                        'secret': 'c', 'disallowed': ['c1', 'c2']}]
            publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                        'utcTimeout': 30}]
            self.assertGiTxQueueMsgs(env.txq, [
                TimerRequest(30, env.room.turnMgr.timerExpiredCb, {
                                "turnId": 1,
                             }),
                ClientTxMsg(secretMsg, {201}),
                ClientTxMsg(secretMsg, {101, 102}),
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
            ], anyOrder=True)
            self.assertEqual(env.room.teams[2].members['jg1'].turnsPlayed, 0)

            # Invalid turnId
            env.room.turnMgr.timerExpiredCb({"turnId": 5})

            # Valid timer expiry, starts the next turn
            env.room.turnMgr.timerExpiredCb({"turnId": 1})
            publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'TIMED_OUT',
                         'secret': 'c', 'disallowed': ['c1', 'c2'],
                         'score': [1]}]
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                ClientTxMsg(["WAIT-FOR-KICKOFF", 2, "sb1"], {101, 102, 201, 202}, None),
                ClientTxMsg(["SCORE", {1: 1, 2: 0}],
                            {101, 102, 201, 202}),
            ], anyOrder=True)
            self.assertEqual(env.room.teams[2].members['jg1'].turnsPlayed, 1)

            # KICKOFF new turn, discard 1st word, let timer expire on the last word
            env.room.processMsg(ClientRxMsg(["KICKOFF"], 101))
            secretMsg = ['TURN', 2, 1, {'team': 1, 'player': 'sb1', 'state': 'IN_PLAY',
                                        'utcTimeout': 31,
                                        'secret': 'a', 'disallowed': ['a1', 'a2']}]
            publicMsg = ['TURN', 2, 1, {'team': 1, 'player': 'sb1', 'state': 'IN_PLAY',
                                        'utcTimeout': 31}]
            self.assertGiTxQueueMsgs(env.txq, [
                TimerRequest(30, env.room.turnMgr.timerExpiredCb, {
                                "turnId": 2,
                             }),
                ClientTxMsg(secretMsg, {101}),
                ClientTxMsg(secretMsg, {201, 202}),
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
            ], anyOrder=True)

            env.room.processMsg(ClientRxMsg(["DISCARD", 2, 1], 101))
            self.drainGiTxQueue(env.txq)

            with stub(env.room.turnMgr._wordSet, "areWordsAvailable",
                      lambda path: False):
                env.room.turnMgr.timerExpiredCb({"turnId": 2})
                publicMsg = ['TURN', 2, 2, {'team': 1, 'player': 'sb1', 'state': 'TIMED_OUT',
                             'secret': 'b', 'disallowed': ['b1', 'b2'],
                             'score': [2]}]
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                    ClientTxMsg(["SCORE", {1: 1, 2: 2}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["GAME-OVER", [2]], {101, 102, 201, 202}),
                    InternalGiStatus([
                        {"hostParameters": {"numTeams": 2,
                                            "turnDurationSec": 30,
                                            "wordSets": ["test"],
                                            "numTurns": 1},
                         "gameState": "GAME_OVER",
                         "clientCount": {1: {'sb1': 1, 'sb2': 1}, 2: {'jg1': 1, 'jg2': 1}},
                         "winners": [2]
                        }
                    ], "taboo:1"),
                ], anyOrder=True)
                self.assertEqual(env.room.teams[1].members['sb1'].turnsPlayed, 1)

                # Test timer fire after the game is over
                env.room.turnMgr.timerExpiredCb({"turnId": 2})
                self.assertGiTxQueueMsgs(env.txq, [])
                self.assertEqual(env.room.teams[1].members['sb1'].turnsPlayed, 1)

    def testDiscard(self):
        env = self.setUpTabooRoom()
        self.drainGiTxQueue(env.txq)

        with stubs([(SupportedWordSets["test"], "nextWord", self.mockNextWord),
                    (Taboo.TurnManager, "expiryEpoch", stubExpiryEpochGen())]):
            env.room.processMsg(ClientRxMsg(["DISCARD"], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["DISCARD-BAD", "Invalid message length"], {101}, 101),
            ])

            env.room.processMsg(ClientRxMsg(["DISCARD", "foo", 1], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["DISCARD-BAD", "Invalid message type"], {101}, 101),
            ])

            env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["DISCARD-BAD", "Game not running"], {101}, 101),
            ])

            self.setUpTeamPlayer(env, 1, "sb1", [101])
            self.setUpTeamPlayer(env, 1, "sb2", [102])
            self.setUpTeamPlayer(env, 2, "jg1", [201])
            self.setUpTeamPlayer(env, 2, "jg2", [202])

            def mockFindNextPlayer(remainingPlayers=[
                    env.room.playerByWs[201],
                    env.room.playerByWs[101],
                    env.room.playerByWs[202],
                ]):
                if remainingPlayers:
                    return remainingPlayers.pop(0)
                return None
            with stub(env.room.turnMgr, "_findNextPlayer", mockFindNextPlayer):
                env.room._allPlayersReady()
                self.drainGiTxQueue(env.txq)

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 101))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["DISCARD-BAD", "It is not your turn"], {101}, 101),
                ])

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["DISCARD-BAD", "Can't DISCARD right now"], {201}, 201),
                ])

                # KICKOFF turn
                env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
                self.drainGiTxQueue(env.txq)

                env.room.processMsg(ClientRxMsg(["DISCARD", 0, 1], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["DISCARD-BAD", "Invalid turn"], {201}, 201),
                ])

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 0], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["DISCARD-BAD", "Invalid word"], {201}, 201),
                ])

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["TURN", 1, 1, {"team": 2, "player": "jg1", "state": "DISCARDED",
                                                "secret": "c",
                                                "disallowed": ["c1", "c2"],
                                                "score": [1]}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["SCORE", {1: 1, 2: 0}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                                "utcTimeout": 30}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                                "utcTimeout": 30,
                                                "secret": "a",
                                                "disallowed": ["a1", "a2"]}],
                                {201}),
                    ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                                "utcTimeout": 30,
                                                "secret": "a",
                                                "disallowed": ["a1", "a2"]}],
                                {101, 102}),
                ], anyOrder=True)
                self.assertEqual(env.room.teams[2].members['jg1'].turnsPlayed, 0)

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 2], 201))
                self.drainGiTxQueue(env.txq)

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 3], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["TURN", 1, 3, {"team": 2, "player": "jg1", "state": "DISCARDED",
                                                "secret": "b",
                                                "disallowed": ["b1", "b2"],
                                                "score": [1]}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["SCORE", {1: 3, 2: 0}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["GAME-OVER", [1]],
                                {101, 102, 201, 202}),
                    InternalGiStatus([
                        {"hostParameters": {"numTeams": 2,
                                            "turnDurationSec": 30,
                                            "wordSets": ["test"],
                                            "numTurns": 1},
                         "gameState": "GAME_OVER",
                         "clientCount": {1: {'sb1': 1, 'sb2': 1}, 2: {'jg1': 1, 'jg2': 1}},
                         "winners": [1]
                        }
                    ], "taboo:1"),
                ], anyOrder=True)
                self.assertEqual(env.room.teams[2].members['jg1'].turnsPlayed, 1)

                env.room.processMsg(ClientRxMsg(["DISCARD", 1, 3], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["DISCARD-BAD", "Game not running"],
                                {201}, 201),
                ])

    def testCompleted(self):
        env = self.setUpTabooRoom()
        self.drainGiTxQueue(env.txq)

        with stubs([(SupportedWordSets["test"], "nextWord", self.mockNextWord),
                    (Taboo.TurnManager, "expiryEpoch", stubExpiryEpochGen())]):
            env.room.processMsg(ClientRxMsg(["COMPLETED"], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["COMPLETED-BAD", "Invalid message length"], {101}, 101),
            ])

            env.room.processMsg(ClientRxMsg(["COMPLETED", "foo", 1], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["COMPLETED-BAD", "Invalid message type"], {101}, 101),
            ])

            env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 1], 101))
            self.assertGiTxQueueMsgs(env.txq, [
                ClientTxMsg(["COMPLETED-BAD", "Game not running"], {101}, 101),
            ])

            self.setUpTeamPlayer(env, 1, "sb1", [101])
            self.setUpTeamPlayer(env, 1, "sb2", [102])
            self.setUpTeamPlayer(env, 2, "jg1", [201])
            self.setUpTeamPlayer(env, 2, "jg2", [202])

            def mockFindNextPlayer(remainingPlayers=[
                    env.room.playerByWs[201],
                    env.room.playerByWs[101],
                    env.room.playerByWs[202],
                ]):
                if remainingPlayers:
                    return remainingPlayers.pop(0)
                return None
            with stub(env.room.turnMgr, "_findNextPlayer", mockFindNextPlayer):
                env.room._allPlayersReady()
                self.drainGiTxQueue(env.txq)

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 1], 101))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["COMPLETED-BAD", "It is not your turn"], {101}, 101),
                ])

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 1], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["COMPLETED-BAD", "Can't COMPLETED right now"], {201}, 201), #sic
                ])

                # KICKOFF turn
                env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
                self.drainGiTxQueue(env.txq)

                env.room.processMsg(ClientRxMsg(["COMPLETED", 0, 1], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["COMPLETED-BAD", "Invalid turn"], {201}, 201),
                ])

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 0], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["COMPLETED-BAD", "Invalid word"], {201}, 201),
                ])

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 1], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["TURN", 1, 1, {"team": 2, "player": "jg1", "state": "COMPLETED",
                                                "secret": "c",
                                                "disallowed": ["c1", "c2"],
                                                "score": [2]}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["SCORE", {1: 0, 2: 1}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                                "utcTimeout": 30}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                                "utcTimeout": 30,
                                                "secret": "a",
                                                "disallowed": ["a1", "a2"]}],
                                {201}),
                    ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                                "utcTimeout": 30,
                                                "secret": "a",
                                                "disallowed": ["a1", "a2"]}],
                                {101, 102}),
                ], anyOrder=True)
                self.assertEqual(env.room.teams[2].members['jg1'].turnsPlayed, 0)

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 2], 201))
                self.drainGiTxQueue(env.txq)

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 3], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["TURN", 1, 3, {"team": 2, "player": "jg1", "state": "COMPLETED",
                                                "secret": "b",
                                                "disallowed": ["b1", "b2"],
                                                "score": [2]}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["SCORE", {1: 0, 2: 3}],
                                {101, 102, 201, 202}),
                    ClientTxMsg(["GAME-OVER", [2]],
                                {101, 102, 201, 202}),
                    InternalGiStatus([
                        {"hostParameters": {"numTeams": 2,
                                            "turnDurationSec": 30,
                                            "wordSets": ["test"],
                                            "numTurns": 1},
                         "gameState": "GAME_OVER",
                         "clientCount": {1: {'sb1': 1, 'sb2': 1}, 2: {'jg1': 1, 'jg2': 1}},
                         "winners": [2]
                        }
                    ], "taboo:1"),
                ], anyOrder=True)
                self.assertEqual(env.room.teams[2].members['jg1'].turnsPlayed, 1)

                env.room.processMsg(ClientRxMsg(["COMPLETED", 1, 3], 201))
                self.assertGiTxQueueMsgs(env.txq, [
                    ClientTxMsg(["COMPLETED-BAD", "Game not running"],
                                {201}, 201),
                ])

class TabooWordTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        self.txq = asyncio.Queue()

    def setUpWord(self, turnId=1, wordId=1,
                  secret=None, disallowed=None,
                  player=None, otherTeams=None,
                  allConns=None,
                  state=WordState.IN_PLAY,
                  utcTimeout=30,
                  score=None,
                  playerName="sb", playerTeamNum=1, playerWss=None,
                  otherTeamNum=2, otherTeamWss=None):
        # pylint: disable=too-many-locals
        secret = secret or "a"
        disallowed = disallowed or ["a1", "a2"]

        playerWss = playerWss or {101} # 1 player
        otherTeamWss = otherTeamWss or {102} # 1 other team member

        allConns = Connections(self.txq)
        for ws in playerWss | otherTeamWss | {103}: # 1 spectator added
            allConns.addConn(ws)

        playerTeam = TabooTeam(self.txq, allConns, playerTeamNum)
        player = TabooPlayer(self.txq, allConns, name=playerName, team=playerTeam)
        for ws in playerWss:
            player.addConn(ws)

        otherTeam = TabooTeam(self.txq, allConns, otherTeamNum)
        for ws in otherTeamWss:
            otherTeam.conns.addConn(ws)

        otherTeams = [otherTeam]
        score = score or []

        return Word(turnId=turnId, wordId=wordId,
                    secret=secret, disallowed=disallowed,
                    player=player, otherTeams=otherTeams,
                    allConns=allConns,
                    utcTimeout=utcTimeout,
                    state=state,
                    score=score)

    def testBasic(self):
        turn = self.setUpWord()

        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TEAM-STATUS", 1, []],
                        {101, 102, 103}),
            ClientTxMsg(["TEAM-STATUS", 1, ['sb']],
                        {101, 102, 103}),
            ClientTxMsg(["TEAM-STATUS", 2, []],
                        {101, 102, 103}),
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "IN_PLAY",
                                        "utcTimeout": 30}],
                        {101, 102, 103}),
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "IN_PLAY",
                                        "utcTimeout": 30,
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"]}],
                        {101}),
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "IN_PLAY",
                                        "utcTimeout": 30,
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"]}],
                        {102}),
            ClientTxMsg(["PLAYER-STATUS", "sb", {"numConns": 1,
                                                 "ready": False,
                                                 "turnsPlayed": 0}],
                        {101, 102, 103}),
        ], anyOrder=True)
        self.assertIsNotNone(turn._privateMsgSrc)

        turn._state = WordState.COMPLETED
        turn._score = [1]
        turn.updateMsgs()
        self.assertIsNone(turn._privateMsgSrc) # privateMsgSrc should be deleted
        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "COMPLETED",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"],
                                        "score": [1]}],
                        {101, 102, 103}),
        ], anyOrder=True)

        turn._state = WordState.DISCARDED
        turn._score = [2]
        turn.updateMsgs()
        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "DISCARDED",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"],
                                        "score": [2]}],
                        {101, 102, 103}),
        ], anyOrder=True)

        turn._state = WordState.TIMED_OUT
        turn._score = [2]
        turn.updateMsgs()
        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "TIMED_OUT",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"],
                                        "score": [2]}],
                        {101, 102, 103}),
        ], anyOrder=True)

class TabooWordSetTest(unittest.TestCase):
    def testExhausted(self):
        wordset = SupportedWordSets["test"]

        with stub(wordset, "_usedWordsByRequestor", {"taboo:1": {"a", "b", "c"}}):
            self.assertIsNone(wordset.nextWord("taboo:1"))

    def testBasic(self):
        wordset = SupportedWordSets["test"]

        def tryNextWord(usedWords, possibleValues, requestor="taboo:1"):
            with stub(wordset, "_usedWordsByRequestor", {requestor: usedWords}):
                found = wordset.nextWord(requestor)
                self.assertIn((found.word, found.disallowed), possibleValues)

        tryNextWord({"b", "c"}, [("a", ["a1", "a2"])])
        tryNextWord({"a", "c"}, [("b", ["b1", "b2"])])
        tryNextWord({"a", "b"}, [("c", ["c1", "c2"])])

        tryNextWord({"a"}, [("b", ["b1", "b2"]), ("c", ["c1", "c2"])])

class TabooTurnManagerTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        def mockNextWord(requestor, remainingWords=[ # pylint: disable= unused-argument
                            Map(word="c", disallowed=["c1", "c2"]),
                            Map(word="a", disallowed=["a1", "a2"]),
                            Map(word="b", disallowed=["b1", "b2"]),
                         ]):
            return remainingWords.pop(0)
        self.mockNextWord = mockNextWord

    def testBasic(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]
        with stub(wordset, "nextWord", self.mockNextWord):
            allConns = Connections(txq)
            team1 = mockPlyrTeam(txq, allConns, 1, {"sb1": [101], "sb2": [102]}, {})
            team2 = mockPlyrTeam(txq, allConns, 2, {"jg1": [201], "jg2": [202]}, {})

            teams = {1: team1, 2: team2}
            hostParameters = HostParameters(numTeams=2,
                                            turnDurationSec=30,
                                            wordSets=["test"],
                                            numTurns=2)

            for team in teams.values():
                for ws in team.conns._wss:
                    allConns.addConn(ws)
            self.drainGiTxQueue(txq)

            turnMgr = TurnManager("taboo:1", txq, wordset, teams, hostParameters, allConns, None)
            def mockFindNextPlayer():
                return team2.members["jg1"]
            stub1 = stub(turnMgr, "_findNextPlayer", mockFindNextPlayer)
            stub1.__enter__() # pylint: disable=no-member

            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(["SCORE", {1: 0, 2: 0}],
                            {101, 102, 201, 202}),
            ], anyOrder=True)

            self.assertTrue(turnMgr.startNewTurn())
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(["WAIT-FOR-KICKOFF", 1, "jg1"], {101, 102, 201, 202}, None),
            ])

            self.assertTrue(turnMgr.startNextWord())
            secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                        'utcTimeout': None,  # We didn't send KICKOFF explicitly
                                        'secret': 'c', 'disallowed': ['c1', 'c2']}]
            publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                        'utcTimeout': None}]
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                ClientTxMsg(secretMsg, {101, 102}),
                ClientTxMsg(secretMsg, {201}),
            ], anyOrder=True)

    def testEnoughTurnsPlayed(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]

        allConns = Connections(txq)
        team1 = mockPlyrTeam(txq, allConns, 1, {"sb": [101]}, {"sb": 2})
        team2 = mockPlyrTeam(txq, allConns, 2, {"jg": [102]}, {"jg": 2})

        teams = {1: team1, 2: team2}
        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=2)

        for team in teams.values():
            for ws in team.conns._wss:
                allConns.addConn(ws)

        turnMgr = TurnManager("taboo:1", txq, wordset, teams, hostParameters, allConns, None)

        self.assertFalse(turnMgr.startNewTurn())
        self.assertGiTxQueueMsgs(txq, [
            ClientTxMsg(['PLAYER-STATUS', 'jg', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {101}),
            ClientTxMsg(['PLAYER-STATUS', 'sb', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {101}),
            ClientTxMsg(['PLAYER-STATUS', 'jg', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {102}),
            ClientTxMsg(['PLAYER-STATUS', 'sb', {'numConns': 1, 'ready': False, 'turnsPlayed': 0}],
                        {102}),
            ClientTxMsg(["SCORE", {1: 0, 2: 0}],
                        {101, 102}),
        ], anyOrder=True)

    def testRunOutOfWords(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]
        with stub(wordset, "nextWord", self.mockNextWord):
            allConns = Connections(txq)
            team1 = mockPlyrTeam(txq, allConns, 1, {"sb1": [101], "sb2": [102]})
            team2 = mockPlyrTeam(txq, allConns, 2, {"jg1": [201], "jg2": [202]})

            teams = {1: team1, 2: team2}
            hostParameters = HostParameters(numTeams=2,
                                            turnDurationSec=30,
                                            wordSets=["test"],
                                            numTurns=2)

            for team in teams.values():
                for ws in team.conns._wss:
                    allConns.addConn(ws)

            turnMgr = TurnManager("taboo:1", txq, wordset, teams, hostParameters, allConns, None)
            def mockFindNextPlayer(remainingPlayers=[
                    team2.members["jg1"],
                    team1.members["sb1"],
                    team2.members["jg2"],
                ]):
                if remainingPlayers:
                    return remainingPlayers.pop(0)
                return None
            stub1 = stub(turnMgr, "_findNextPlayer", mockFindNextPlayer)
            stub1.__enter__() # pylint: disable=no-member

            self.assertTrue(turnMgr.startNewTurn())
            self.drainGiTxQueue(txq)

            self.assertTrue(turnMgr.startNextWord())
            secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                        'utcTimeout': None, # didn't send KICKOFF explicitly
                                        'secret': 'c', 'disallowed': ['c1', 'c2']}]
            publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                        'utcTimeout': None}]
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                ClientTxMsg(secretMsg, {101, 102}),
                ClientTxMsg(secretMsg, {201}),
            ], anyOrder=True)

            turnMgr._curTurn.player.turnsPlayed += 1
            self.assertTrue(turnMgr.startNewTurn())
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(["WAIT-FOR-KICKOFF", 2, "sb1"], {101, 102, 201, 202}, None),
            ], anyOrder=True)

            self.assertTrue(turnMgr.startNextWord())
            secretMsg = ['TURN', 2, 1, {'team': 1, 'player': 'sb1', 'state': 'IN_PLAY',
                                        'utcTimeout': None, # didn't send KICKOFF explicitly
                                        'secret': 'a', 'disallowed': ['a1', 'a2']}]
            publicMsg = ['TURN', 2, 1, {'team': 1, 'player': 'sb1', 'state': 'IN_PLAY',
                                        'utcTimeout': None}]
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                ClientTxMsg(secretMsg, {201, 202}),
                ClientTxMsg(secretMsg, {101}),
            ], anyOrder=True)

            turnMgr._curTurn.player.turnsPlayed += 1
            self.assertTrue(turnMgr.startNewTurn())
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(["WAIT-FOR-KICKOFF", 3, "jg2"], {101, 102, 201, 202}, None),
            ], anyOrder=True)

            self.assertTrue(turnMgr.startNextWord())
            secretMsg = ['TURN', 3, 1, {'team': 2, 'player': 'jg2', 'state': 'IN_PLAY',
                                        'utcTimeout': None, # didn't send KICKOFF explicitly
                                        'secret': 'b', 'disallowed': ['b1', 'b2']}]
            publicMsg = ['TURN', 3, 1, {'team': 2, 'player': 'jg2', 'state': 'IN_PLAY',
                                        'utcTimeout': None}]
            self.assertGiTxQueueMsgs(txq, [
                ClientTxMsg(publicMsg, {101, 102, 201, 202}),
                ClientTxMsg(secretMsg, {101, 102}),
                ClientTxMsg(secretMsg, {202}),
            ], anyOrder=True)

            turnMgr._curTurn.player.turnsPlayed += 1
            self.assertFalse(turnMgr.startNewTurn())

    def testNoClients(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]
        allConns = Connections(txq)

        team1 = mockPlyrTeam(txq, allConns, 1, {"sb": []})
        team2 = mockPlyrTeam(txq, allConns, 2, {"jg": []})

        teams = {1: team1, 2: team2}
        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=1)

        for team in teams.values():
            for ws in team.conns._wss:
                allConns.addConn(ws)

        turnMgr = TurnManager("taboo:1", txq, wordset, teams, hostParameters, allConns, None)

        self.assertFalse(turnMgr.startNewTurn())
        self.assertGiTxQueueMsgs(txq, [])
