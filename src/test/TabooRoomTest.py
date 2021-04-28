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

class TabooRoomTest(unittest.TestCase, MsgTestLib):
    def setUp(self):
        pass

    def setUpTabooRoom(self):
        rxq = asyncio.Queue()
        txq = asyncio.Queue()

        hostParameters = HostParameters(numTeams=2,
                                        turnDurationSec=30,
                                        wordSets=["foo"])
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
                                    "wordSets": ["foo"]},
                 "clientCount": 0}
            ], "taboo:1"),
        ], anyOrder=True)

        ws1 = 1
        env.room.processConnect(ws1)

        self.assertGiTxQueueMsgs(env.txq, [
            ClientTxMsg(['HOST-PARAMETERS', {'numTeams': 2,
                                             'turnDurationSec': 30,
                                             'wordSets': ['foo']}], {ws1}),
            InternalGiStatus([
                {"hostParameters": {"numTeams": 2,
                                    "turnDurationSec": 30,
                                    "wordSets": ["foo"]},
                 "clientCount": 1}
            ], "taboo:1"),
        ], anyOrder=True)
