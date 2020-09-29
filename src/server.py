#!/usr/bin/env python3

"""
Websocket managing server that dispatches messages
from clients to the correct game instance and vice
versa.
"""

import asyncio
import json
import websockets

from fwk.ServerQueueTask import (
        clientTxMsg,
        clientTxQueueAdd,
        clientTxQueueRemove,
        giByPath,
        giRxMsg,
        registerGameClass,
        txQueue,
        wsPathAdd,
        wsPathRemove,
)
from fwk.LobbyPlugin import LOBBY_PATH
from fwk.Msg import (
        InternalConnectWsToGi,
        InternalDisconnectWsToGi,
        InternalGiStatus,
        InternalHost,
        InternalRegisterGi,
        ClientRxMsg,
        ClientTxMsg,
)
from fwk.MsgType import (
        MTYPE_ERROR,
)
import fwk.LobbyPlugin
import Chat.ChatLobbyPlugin
import Dirty7.Dirty7Lobby


async def rxClient(clientWs, path):
    """
    Method to handle each client websocket connecting to
    the server.
    """
    path = path.strip("/")

    # GxRxQueue + task must exist if the path is valid in this check
    if giByPath(path) is None:
        await clientWs.send(json.dumps([MTYPE_ERROR, "Bad path"]))
        return

    # Register ws <--> path
    wsPathAdd(clientWs, path)

    # Queue+task for messages to ws
    clientTxQueueAdd(clientWs)

    # Queue+task
    giRxMsg(path, InternalConnectWsToGi(clientWs))

    try:
        async for message in clientWs:
            try:
                jmsg = json.loads(message)
            except json.decoder.JSONDecodeError:
                await clientTxMsg([MTYPE_ERROR, "Bad JSON message"], clientWs)
                continue

            if not isinstance(jmsg, list):
                await clientTxMsg([MTYPE_ERROR, "Bad message: not a list"], clientWs)
                continue

            if not jmsg:
                await clientTxMsg([MTYPE_ERROR, "Bad message: empty list"], clientWs)
                continue

            giRxMsg(path, ClientRxMsg(jmsg, initiatorWs=clientWs))

    except websockets.exceptions.ConnectionClosedError:
        pass

    giRxMsg(path, InternalDisconnectWsToGi(clientWs))

    wsPathRemove(clientWs, path)

    clientTxQueueRemove(clientWs)

async def giTxQueue(queue):
    """
    Task to drain the queue with messages from game instances.
    These messages can be meant for other game instances (only lobby)
    or to client websockets.
    """
    while True:
        qmsg = await queue.get()
        queue.task_done()

        if isinstance(qmsg, InternalHost):
            if giByPath(qmsg.path) is None:
                await clientTxMsg("Bad path", qmsg.initiatorWs)
                continue
            giRxMsg(qmsg.path, qmsg)
            continue

        if isinstance(qmsg, InternalRegisterGi):
            registerGameClass(qmsg.gi)
            continue

        if isinstance(qmsg, InternalGiStatus):
            giRxMsg(LOBBY_PATH, qmsg)
            continue

        msg = json.dumps(qmsg.jmsg)

        assert isinstance(qmsg, ClientTxMsg)
        for toWs in qmsg.toWss:
            await clientTxMsg(msg, toWs)


def main():
    """Initialize websocket serving server and load plugins"""
    wsServer = websockets.serve(rxClient, "0.0.0.0", 4000)

    asyncio.get_event_loop().create_task(giTxQueue(txQueue()))

    registerGameClass(fwk.LobbyPlugin.plugin())
    registerGameClass(Chat.ChatLobbyPlugin.plugin())
    registerGameClass(Dirty7.Dirty7Lobby.plugin())

    asyncio.get_event_loop().run_until_complete(wsServer)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
