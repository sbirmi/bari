"""Dirty7 lobby. This allows hosting/creating Dirty7Rooms"""

from fwk.GamePlugin import GameLobbyPlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalRegisterGi,
)
from fwk.MsgType import MTYPE_HOST_BAD
from Dirty7.Exceptions import InvalidDataException
from Dirty7.Dirty7Round import RoundParameters
from Dirty7.Dirty7Room import Dirty7Room


class Dirty7Lobby(GameLobbyPlugin):
    """Hosting lobby for Dirty7"""
    gameIdx = 0
    rooms = {}

    def processHost(self, qmsg):
        try:
            roundParameters = RoundParameters.fromJmsg(qmsg.jmsg)
        except InvalidDataException as exc:
            self.txQueue.put_nowait(ClientTxMsg(
                [MTYPE_HOST_BAD] + exc.toJmsg(), {qmsg.initiatorWs},
                initiatorWs=qmsg.initiatorWs))
            return True

        self.gameIdx += 1
        newRoom = Dirty7Room("dirty7:{}".format(self.gameIdx),
                             "Dirty7 Room #{}".format(self.gameIdx),
                             roundParameters)
        self.rooms[self.gameIdx] = newRoom

        self.txQueue.put_nowait(InternalRegisterGi(newRoom, initiatorWs=qmsg.initiatorWs))
        return True

def plugin(): # pylint: disable=missing-function-docstring
    return Dirty7Lobby("dirty7", "Dirty7")
