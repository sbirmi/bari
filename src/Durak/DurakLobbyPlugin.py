"""Durak lobby plugin. This allows hosting/creating DurakRooms"""
from fwk.Exceptions import InvalidDataException
from fwk.GamePlugin import GameLobbyPlugin
from fwk.Msg import (
        ClientTxMsg,
        InternalRegisterGi,
)
from fwk.MsgType import MTYPE_HOST_BAD
from Durak.Room import Room
from Durak.RoundParameters import RoundParameters


class DurakLobbyPlugin(GameLobbyPlugin):
    """Game lobby for chat rooms"""
    gameIdx = 0
    rooms = {}

    def processHost(self, qmsg):
        """
        original_message = [
        "HOST", "durak",
        {"numPlayers": <int>,
         "stopPoints": <int>,
        }]
        """
        try:
            hostParameters = RoundParameters.fromJmsg(qmsg.jmsg)
        except InvalidDataException as exc:
            self.txQueue.put_nowait(ClientTxMsg(
                [MTYPE_HOST_BAD] + exc.toJmsg(), {qmsg.initiatorWs},
                initiatorWs=qmsg.initiatorWs))
            return True

        self.gameIdx += 1

        newRoom = Room(f"durak:{self.gameIdx}",
                       f"Durak Room #{self.gameIdx}",
                       hostParameters)
        self.rooms[self.gameIdx] = newRoom
        self.txQueue.put_nowait(InternalRegisterGi(newRoom, initiatorWs=qmsg.initiatorWs))

        return True
#
#        if qmsg.jmsg:
#            self.txQueue.put_nowait(ClientTxMsg(
#                [MTYPE_HOST_BAD, "Unexpected parameters"], {qmsg.initiatorWs},
#                initiatorWs=qmsg.initiatorWs))
#            return True
#
#        self.gameIdx += 1
#        newRoom = DurakRoom("durak:{}".format(self.gameIdx),
#                           "Durak Room #{}".format(self.gameIdx))
#        self.rooms[self.gameIdx] = newRoom
#
#        self.txQueue.put_nowait(InternalRegisterGi(newRoom,
#                                                   initiatorWs=qmsg.initiatorWs))
#        return True


def plugin(): # pylint: disable=missing-function-docstring
    return DurakLobbyPlugin("durak", "The Durak Game")
