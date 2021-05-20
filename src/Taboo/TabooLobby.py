"""Taboo lobby. This allows hosting/creating TabooRooms"""

from fwk.Exceptions import InvalidDataException
from fwk.GamePlugin import GameLobbyPlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalRegisterGi,
)
from fwk.MsgType import MTYPE_HOST_BAD
from fwk.Trace import (
        Level,
        trace,
)

from Taboo.HostParameters import HostParameters
from Taboo.TabooRoom import TabooRoom
from Taboo.WordSets import SupportedWordSets

class TabooLobby(GameLobbyPlugin):
    """Lobby for Taboo"""
    gameIdx = 0
    rooms = {}

    def processHost(self, qmsg):
        """
        original_message = [
            "HOST", "taboo",
            {"numTeams": <int>,         # 1..4
             "turnDurationSec": <int>,  # 30..180
             "wordSets": ["name1", "name2", ...]}]

        qmsg.jmsg = original_message[2:]
        """
        try:
            hostParameters = HostParameters.fromJmsg(qmsg.jmsg)
        except InvalidDataException as exc:
            self.txQueue.put_nowait(ClientTxMsg(
                [MTYPE_HOST_BAD] + exc.toJmsg(), {qmsg.initiatorWs},
                initiatorWs=qmsg.initiatorWs))
            return True

        self.gameIdx += 1

        newRoom = TabooRoom("taboo:{}".format(self.gameIdx),
                            "Taboo Room #{}".format(self.gameIdx),
                            hostParameters)
        self.rooms[self.gameIdx] = newRoom
        self.txQueue.put_nowait(InternalRegisterGi(newRoom, initiatorWs=qmsg.initiatorWs))

        return True

    def processRefresh(self, qmsg):
        if qmsg.jmsg[1] in SupportedWordSets:
            try:
                SupportedWordSets[qmsg.jmsg[1]].loadData()
            except Exception as exc: # pylint: disable=broad-except
                trace(Level.error, "Failed to refresh", qmsg.jmsg[1], str(exc))
                self.txQueue.put_nowait(
                        ClientTxMsg(["REFRESH-BAD"],
                                    {qmsg.initiatorWs},
                                    initiatorWs=qmsg.initiatorWs))

        return False # Pretend message wasn't understood

    def processMsg(self, qmsg):
        if super(TabooLobby, self).processMsg(qmsg):
            return True

        # [ "REFRESH", "WordSetFileName" ]
        if (isinstance(qmsg.jmsg, list) and
                len(qmsg.jmsg) == 2 and
                qmsg.jmsg[0] == "REFRESH" and
                isinstance(qmsg.jmsg[1], str)):
            return self.processRefresh(qmsg)

        return False

def plugin():
    """Register with bari server"""
    return TabooLobby("taboo", "Taboo")
