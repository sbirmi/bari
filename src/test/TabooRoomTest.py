import asyncio
import unittest

from test.MsgTestLib import MsgTestLib
from fwk.Common import Map
from fwk.Msg import (
        ClientTxMsg,
        InternalGiStatus,
)
from fwk.MsgSrc import Connections
from Taboo import TabooRoom
from Taboo.HostParameters import HostParameters
from Taboo.TabooPlayer import TabooPlayer
from Taboo.TabooTeam import TabooTeam
from Taboo.Turn import (
        Turn,
        TurnState,
)

class TabooRoomTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        pass

    def setUpTabooRoom(self):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["foo"],
                                        numRounds=1)
        room = TabooRoom.TabooRoom("taboo:1", "Taboo Room #1", hostParameters)
        room.setRxTxQueues(rxq, txq)

        return Map(rxq=rxq,
                   txq=txq,
                   hostParameters=hostParameters,
                   room=room)

    def testNewGame(self):
        env = self.setUpTabooRoom()

        self.assertGiTxQueueMsgs(env.txq, [
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["foo"],
                                    "numRounds": 1},
                 "clientCount": 0}
            ], "taboo:1"),
        ], anyOrder=True)

        ws1 = 1
        env.room.processConnect(ws1)

        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(['HOST-PARAMETERS', {'numTeams': 2,
                                             'turnDurationSec': 30,
                                             'wordSets': ['foo'],
                                             'numRounds': 1}], {ws1}),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["foo"],
                                    "numRounds": 1},
                 "clientCount": 1}
            ], "taboo:1"),
        ], anyOrder=True)

class TabooTurnTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        self.txq = asyncio.Queue()

    def setUpTurn(self, turnId=1, wordId=1,
                  secret=None, disallowed=None,
                  player=None, otherTeams=None,
                  allConns=None,
                  state=TurnState.IN_PLAY,
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
            player.playerConns.addConn(ws)

        otherTeam = TabooTeam(self.txq, otherTeamNum)
        for ws in otherTeamWss:
            otherTeam.conns.addConn(ws)

        otherTeams = [otherTeam]
        score = score or []

        return Turn(turnId=turnId, wordId=wordId,
                    secret=secret, disallowed=disallowed,
                    player=player, otherTeams=otherTeams,
                    allConns=allConns,
                    state=state,
                    score=score)

    def testBasic(self):
        # pylint: disable=protected-access
        turn = self.setUpTurn()

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

        turn._state = TurnState.COMPLETED
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

        turn._state = TurnState.DISCARDED
        turn._score = [2]
        turn.updateMsgs()
        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "DISCARDED",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"],
                                        "score": [2]}],
                        {101, 102, 103}),
        ], anyOrder=True)

        turn._state = TurnState.TIMED_OUT
        turn._score = [2]
        turn.updateMsgs()
        self.assertGiTxQueueMsgs(self.txq, [
            ClientTxMsg(["TURN", 1, 1, {"team": 1, "player": "sb", "state": "TIMED_OUT",
                                        "secret": "a",
                                        "disallowed": ["a1", "a2"],
                                        "score": [2]}],
                        {101, 102, 103}),
        ], anyOrder=True)
