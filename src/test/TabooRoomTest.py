import asyncio
import random
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
from Taboo.TurnManager import TurnManager
from Taboo.WordSets import SupportedWordSets

# pylint: disable=protected-access

def mockPlyrTeam(txq, teamId,
                 connsByPlayerName,
                 turnsPlayedByPlayerName=None):
    turnsPlayedByPlayerName = turnsPlayedByPlayerName or {}

    team = TabooTeam(txq, teamId)
    for plyrName, conns in connsByPlayerName.items():
        plyr = TabooPlayer(txq, name=plyrName, team=team)
        for ws in conns:
            plyr.addConn(ws)
            team.conns.addConn(ws)

        plyr.turnsPlayed = turnsPlayedByPlayerName.get(plyrName, 0)
    return team

class TabooRoomTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        random.seed(1)

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
            assert ws not in env.room.teams[teamId].conns._wss
            env.room.teams[teamId].conns.addConn(ws) # HACK
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
                 "clientCount": 0}
            ], "taboo:1"),
        ], anyOrder=True)

        ws1 = 1
        env.room.processConnect(ws1)

        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(['HOST-PARAMETERS', {'numTeams': 2,
                                             'turnDurationSec': 30,
                                             'wordSets': ['test'],
                                             'numTurns': 1}], {ws1}),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "WAITING_TO_START",
                 "clientCount": 1}
            ], "taboo:1"),
        ], anyOrder=True)

    def testKickoff(self):
        env = self.setUpTabooRoom()
        self.drainGiTxQueue(env.txq)

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

        env.room.turnMgr.startNewTurn()
        env.room.processMsg(ClientRxMsg(["KICKOFF"], 101))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["WAIT-FOR-KICKOFF", 1, "jg1"], {101, 102, 201, 202}, None),
            ClientTxMsg(["KICKOFF-BAD", "It is not your turn"], {101}, 101),
        ])

        env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
        secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                     'secret': 'c', 'disallowed': ['c1', 'c2']}]
        publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY'}]
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

    def testDiscard(self):
        env = self.setUpTabooRoom()
        self.drainGiTxQueue(env.txq)

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
        env.room._allPlayersReady()
        self.drainGiTxQueue(env.txq)

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 101))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["DISCARD-BAD", "It is not your turn"], {101}, 101),
        ])

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 201))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["DISCARD-BAD", "Can't discard right now"], {201}, 201),
        ])

        # KICKOFF turn
        env.room.processMsg(ClientRxMsg(["KICKOFF"], 201))
        self.drainGiTxQueue(env.txq)

        env.room.processMsg(ClientRxMsg(["DISCARD", 0, 1], 201))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["DISCARD-BAD", "Discarding invalid turn"], {201}, 201),
        ])

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 0], 201))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["DISCARD-BAD", "Discarding invalid word"], {201}, 201),
        ])

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 1], 201))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 2, "player": "jg1", "state": "DISCARDED",
                                        "secret": "c",
                                        "disallowed": ["c1", "c2"],
                                        "score": [1]}],
                        {101, 102, 201, 202}),
            ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY"}],
                        {101, 102, 201, 202}),
            ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"]}],
                        {201}),
            ClientTxMsg(["TURN", 1, 2, {"team": 2, "player": "jg1", "state": "IN_PLAY",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"]}],
                        {101, 102}),
        ], anyOrder=True)

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 2], 201))
        self.drainGiTxQueue(env.txq)

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 3], 201))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["TURN", 1, 3, {"team": 2, "player": "jg1", "state": "DISCARDED",
                                        "secret": "b",
                                        "disallowed": ["b1", "b2"],
                                        "score": [1]}],
                        {101, 102, 201, 202}),
            ClientTxMsg(["GAME-OVER"],
                        {101, 102, 201, 202}),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["test"],
                                    "numTurns": 1},
                 "gameState": "GAME_OVER",
                 "clientCount": 4}
            ], "taboo:1"),
        ], anyOrder=True)

        env.room.processMsg(ClientRxMsg(["DISCARD", 1, 3], 201))
        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(["DISCARD-BAD", "Game not running"],
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

        playerTeam = TabooTeam(self.txq, playerTeamNum)
        player = TabooPlayer(self.txq, name=playerName, team=playerTeam)
        for ws in playerWss:
            player.addConn(ws)

        otherTeam = TabooTeam(self.txq, otherTeamNum)
        for ws in otherTeamWss:
            otherTeam.conns.addConn(ws)

        otherTeams = [otherTeam]
        score = score or []

        return Word(turnId=turnId, wordId=wordId,
                    secret=secret, disallowed=disallowed,
                    player=player, otherTeams=otherTeams,
                    allConns=allConns,
                    state=state,
                    score=score)

    def testBasic(self):
        turn = self.setUpWord()

        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "IN_PLAY"}],
                        {101, 102, 103}),
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "IN_PLAY",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"]}],
                        {101}),
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "IN_PLAY",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"]}],
                        {102}),
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
    def testBasic(self):
        wordset = SupportedWordSets["test"]

        self.assertIsNone(wordset.nextWord({0, 1, 2}))
        self.assertIsNone(wordset.nextWord({0, 1, 2, 3}))

        def tryNextWord(usedWordIdxs, possibleValues):
            found = wordset.nextWord(usedWordIdxs)
            self.assertIn((found.word, found.disallowed), possibleValues)
            self.assertEqual(len(found.usedWordIdxs - usedWordIdxs), 1)

        tryNextWord({1, 2}, [("a", ["a1", "a2"])])
        tryNextWord({0, 2}, [("b", ["b1", "b2"])])
        tryNextWord({0, 1}, [("c", ["c1", "c2"])])

        tryNextWord({0}, [("b", ["b1", "b2"]), ("c", ["c1", "c2"])])

class TabooTurnManagerTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        random.seed(1)

    def testBasic(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]

        team1 = mockPlyrTeam(txq, 1, {"sb1": [101], "sb2": [102]}, {})
        team2 = mockPlyrTeam(txq, 2, {"jg1": [201], "jg2": [202]}, {})

        teams = {1: team1, 2: team2}
        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=2)

        allConns = Connections(txq)
        for team in teams.values():
            for ws in team.conns._wss:
                allConns.addConn(ws)

        turnMgr = TurnManager(txq, wordset, teams, hostParameters, allConns)
        self.assertGiTxQueueMsgs(txq, [])

        self.assertTrue(turnMgr.startNewTurn())
        self.assertGiTxQueueMsgs(txq, [
            ClientTxMsg(["WAIT-FOR-KICKOFF", 1, "jg1"], {101, 102, 201, 202}, None),
        ])

        self.assertTrue(turnMgr.startNextWord())
        secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                    'secret': 'c', 'disallowed': ['c1', 'c2']}]
        publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY'}]
        self.assertGiTxQueueMsgs(txq, [
            ClientTxMsg(publicMsg, {101, 102, 201, 202}),
            ClientTxMsg(secretMsg, {101, 102}),
            ClientTxMsg(secretMsg, {201}),
        ], anyOrder=True)

    def testEnoughTurnsPlayed(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]

        team1 = mockPlyrTeam(txq, 1, {"sb": [101]}, {"sb": 2})
        team2 = mockPlyrTeam(txq, 2, {"jg": [102]}, {"jg": 2})

        teams = {1: team1, 2: team2}
        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=2)

        allConns = Connections(txq)
        for team in teams.values():
            for ws in team.conns._wss:
                allConns.addConn(ws)

        turnMgr = TurnManager(txq, wordset, teams, hostParameters, allConns)

        self.assertFalse(turnMgr.startNewTurn())
        self.assertGiTxQueueMsgs(txq, [])

    def testRunOutOfWords(self):
        txq = asyncio.Queue()
        wordset = SupportedWordSets["test"]

        team1 = mockPlyrTeam(txq, 1, {"sb1": [101], "sb2": [102]})
        team2 = mockPlyrTeam(txq, 2, {"jg1": [201], "jg2": [202]})

        teams = {1: team1, 2: team2}
        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=2)

        allConns = Connections(txq)
        for team in teams.values():
            for ws in team.conns._wss:
                allConns.addConn(ws)

        turnMgr = TurnManager(txq, wordset, teams, hostParameters, allConns)

        self.assertTrue(turnMgr.startNewTurn())
        self.drainGiTxQueue(txq)

        self.assertTrue(turnMgr.startNextWord())
        secretMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY',
                                    'secret': 'c', 'disallowed': ['c1', 'c2']}]
        publicMsg = ['TURN', 1, 1, {'team': 2, 'player': 'jg1', 'state': 'IN_PLAY'}]
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
                                    'secret': 'a', 'disallowed': ['a1', 'a2']}]
        publicMsg = ['TURN', 2, 1, {'team': 1, 'player': 'sb1', 'state': 'IN_PLAY'}]
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
                                    'secret': 'b', 'disallowed': ['b1', 'b2']}]
        publicMsg = ['TURN', 3, 1, {'team': 2, 'player': 'jg2', 'state': 'IN_PLAY'}]
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

        team1 = mockPlyrTeam(txq, 1, {"sb": []})
        team2 = mockPlyrTeam(txq, 2, {"jg": []})

        teams = {1: team1, 2: team2}
        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["test"],
                                        numTurns=1)

        allConns = Connections(txq)
        for team in teams.values():
            for ws in team.conns._wss:
                allConns.addConn(ws)

        turnMgr = TurnManager(txq, wordset, teams, hostParameters, allConns)

        self.assertFalse(turnMgr.startNewTurn())
        self.assertGiTxQueueMsgs(txq, [])
