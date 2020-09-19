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
#        socketsByPath,
        txQueue,
        wsPathAdd,
        wsPathRemove,
)
from fwk.Msg import (
        InternalConnectWsToGi,
        InternalDisconnectWsToGi,
        InternalRegisterGi,
        MsgFromWs,
        MsgToWs,
)


import fwk.LobbyPlugin
import Chat.ChatLobbyPlugin


LOBBY = "lobby"


async def rxClient(clientWs, path):
    """
    Method to handle each client websocket connecting to
    the server.
    """
    path = path.strip("/")

    if giByPath(path) is None:
        await clientTxMsg(clientWs, "Bad path")
        return

    # GxRxQueue + task must exist if the path is valid in the check above

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
                await clientTxMsg(clientWs, "Bad JSON message")
                continue

            if not isinstance(jmsg, list):
                await clientTxMsg(clientWs, "Bad message: not a list")
                continue

            if len(jmsg) <= 1:
                await clientTxMsg(clientWs, "Bad message: empty list")
                continue

            if giByPath(jmsg[0]) is None:
                await clientTxMsg(clientWs, "Unknown path")
                continue

            giRxMsg(jmsg[0], MsgFromWs(clientWs, jmsg))
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

        if isinstance(qmsg, InternalRegisterGi):
            registerGameClass(qmsg.gi)
            continue

        msg = json.dumps(qmsg.jmsg)

#        if isinstance(qmsg, MsgToPath):
#            sockets = socketsByPath(LOBBY_PATH)
#            for ws in sockets:
#                await clientTxMsg(ws, msg)
#            continue

        assert isinstance(qmsg, MsgToWs)
        await clientTxMsg(qmsg.ws, msg)


def main():
    """Initialize websocket serving server and load plugins"""
    wsServer = websockets.serve(rxClient, "0.0.0.0", 4000)

    asyncio.get_event_loop().create_task(giTxQueue(txQueue()))

    registerGameClass(fwk.LobbyPlugin.plugin())
    registerGameClass(Chat.ChatLobbyPlugin.plugin())

    asyncio.get_event_loop().run_until_complete(wsServer)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
