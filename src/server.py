#!/usr/bin/env python3

"""
Websocket managing server that dispatches messages
from clients to the correct game instance and vice
versa.
"""

from argparse import ArgumentParser
import asyncio
import itertools
import json
import websockets

from config import (
        WS_SERVER_PORT_DEFAULT,
)
from fwk.ServerQueueTask import (
        clientTxMsg,
        clientTxQueueAdd,
        clientTxQueueRemove,
        giByPath,
        giRxMsg,
        registerGameClass,
        timerAdd,
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
        TimerRequest,
)
from fwk.MsgType import (
        MTYPE_ERROR,
)
import fwk.LobbyPlugin
from fwk.Trace import (
        Level,
        setTraceFile,
        trace,
)
import Chat.ChatLobbyPlugin
import Dirty7.Dirty7Lobby
import Taboo.TabooLobby


WsIdAllocator = itertools.count()
def nextWsId():
    return next(WsIdAllocator)

def wsSetBariName(ws):
    assert not hasattr(ws, "bari_name")
    wsId = nextWsId()
    ws.bari_name = "#{}/{}:{}" .format(wsId, ws.remote_address[0], ws.remote_address[1])
    ws.__class__.__str__ = lambda ws: ws.bari_name

async def rxClient(clientWs, path):
    """
    Method to handle each client websocket connecting to
    the server.
    """
    path = path.strip("/")
    wsSetBariName(clientWs)

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

        if isinstance(qmsg, TimerRequest):
            await timerAdd(qmsg)
            continue

        try:
            msg = json.dumps(qmsg.jmsg)
        except TypeError as exc:
            trace(Level.error, "Error serializing as JSON:", str(qmsg.jmsg), str(exc))
            continue

        assert isinstance(qmsg, ClientTxMsg)
        for toWs in qmsg.toWss:
            await clientTxMsg(msg, toWs)


def main(wsAddr="0.0.0.0"):
    """Initialize websocket serving server and load plugins"""

    parser = ArgumentParser()
    parser.add_argument("-p", "--port", metavar="PORT",
                        help="Listen port (default={})".format(WS_SERVER_PORT_DEFAULT),
                        default=WS_SERVER_PORT_DEFAULT)
    parser.add_argument("--d7-storage", metavar="SQLITE3_FILE",
                        help="Dirty7 sqlite3 storage file (default={})".format(
                            Dirty7.Dirty7Lobby.DefaultStorageFile),
                        default=Dirty7.Dirty7Lobby.DefaultStorageFile)
    parser.add_argument("--trace-file",
                        help="Trace file (default=STDERR)")

    args = parser.parse_args()
    setTraceFile(args.trace_file)

    trace(Level.info, "Starting server. Listening on", wsAddr, "port", args.port)
    wsServer = websockets.serve(rxClient, wsAddr, args.port) # pylint: disable=no-member

    asyncio.get_event_loop().create_task(giTxQueue(txQueue()))

    plugins = [
            fwk.LobbyPlugin.plugin(),
            Chat.ChatLobbyPlugin.plugin(),
            Dirty7.Dirty7Lobby.plugin(args.d7_storage),
            Taboo.TabooLobby.plugin(),
    ]
    for plugin in plugins:
        registerGameClass(plugin)

    asyncio.get_event_loop().run_until_complete(wsServer)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
