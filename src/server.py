#!/usr/bin/env python3

import asyncio
from collections import defaultdict
import json
import websockets

import Chat.ChatLobbyPlugin

#
#   Client1      Client2
#    ^            ^
#    |            |
#  ClientTx     ClientTx
#  Queue[ws]    Queue[ws]
#    |            |
#  [       MainLoop              ]
#     ^         |             |
#     |         |             |
#     |         v             v
#  common      RxQueue       RxQueue
#  TxQueue     for           for
#  for all     game          game
#  game        instance.     instance.
#  instances.  Element =     Element =
#  Element =    (ws, jmsg)    (ws, jmsg)
#   (wsOrPath,  |             |
#    jmsg)      |             +---> [ game instance 2 ]
#               |
#               +---> [ game instance 1 ]
#

# Queue + task for sending messages to clients asynchronously
ClientTxQueueByWs = {}
ClientTxTaskByWs = {}

# Queue + tasks to talk between the main loop and the game instances
TxQueue = asyncio.Queue()
GiRxQueueByPath = {}
GiRxTaskByPath = {}

# Tracks websockets connected to a given path
wsByPath = defaultdict(set)

# GameInstance by path
GiByPath = {}

def registerGameClass(gameClass):
    print("Registering", gameClass.path, gameClass.name)
    giRxQueue = asyncio.Queue()
    path = gameClass.path

    assert path not in GiByPath
    GiByPath[path] = gameClass

    gameClass.setRxTxQueues(giRxQueue, TxQueue)

    GiRxTaskByPath[path] = \
            asyncio.get_event_loop().create_task(gameClass.worker())

    GiRxQueueByPath[path] = giRxQueue

def registerGameClasses():
    registerGameClass(Chat.ChatLobbyPlugin.plugin())


async def rxClient(clientWs, path):
    path = path.strip("/")

    if path not in GiByPath:
        print("Bad path")
        await clientWs.send("Bad path")
        return

    if path != "lobby":
        GiRxQueueByPath[path].put_nowait((clientWs, [path, "CONNECT"]))

    wsByPath[path].add(clientWs)

    clientTxQueue = asyncio.Queue()
    ClientTxQueueByWs[clientWs] = clientTxQueue
    ClientTxTaskByWs[clientWs] = \
            asyncio.get_event_loop().create_task(
                    clientTxTask(clientTxQueue, clientWs))

    print("Connection from", clientWs, "path", path)

    async for message in clientWs:
        try:
            jmsg = json.loads(message)
        except json.decoder.JSONDecodeError:
            await clientWs.send("Bad JSON message")
            continue

        if not isinstance(jmsg, list):
            await clientWs.send("Bad message: not a list")
            continue

        if len(jmsg) == 0:
            await clientWs.send("Bad message: empty list")
            continue

        # TODO
        # Only path == "lobby" can send messages to other
        # game handles to host games.
        if jmsg[0] not in GiRxQueueByPath:
            await clientWs.send("Unknown path")
            continue

        rxQ = GiRxQueueByPath[jmsg[0]]
        rxQ.put_nowait((clientWs, jmsg))

    if path in GiRxQueueByPath:
        GiRxQueueByPath[path].put_nowait((clientWs, ["DISCONNECT"]))
    else:
        # TODO handle me better
        print("Handle me better")
    wsByPath[path].remove(clientWs)
    del ClientTxQueueByWs[clientWs] 
    ClientTxTaskByWs[clientWs].cancel()
    #await asyncio.gather(ClientTxTaskByWs[clientWs]) # When is this called?
    del ClientTxTaskByWs[clientWs]

    # Client disconnected
    print("Client", clientWs, "disconnected")


async def clientTxTask(queue, clientWs):
    while True:
        msg = await queue.get()
        print("clientTxTask", "Sending:", msg, "to", clientWs)
        await clientWs.send(msg)
        queue.task_done()


async def gameTxQueue(queue):
    while True:
        clientWsOrPath, jmsg = await queue.get()
        queue.task_done()

        if clientWsOrPath == "HOST":
            registerGameClass(jmsg)
            continue

        msg = json.dumps(jmsg)
        print("gameTxQueue got", clientWsOrPath, msg) # Broadcast to lobby semantics

        if isinstance(clientWsOrPath, str):
            if clientWsOrPath not in wsByPath:
                print("Invalid path")
                continue
            for clientWs in wsByPath[clientWsOrPath]:
                ClientTxQueueByWs[clientWs].put_nowait(msg)
            continue

        if clientWsOrPath not in ClientTxQueueByWs:
            print("Invalid clientWsOrPath", clientWsOrPath, ". Msg", msg, "not sent")
            continue

        ClientTxQueueByWs[clientWsOrPath].put_nowait(msg)


def main():
    start_server = websockets.serve(rxClient, "0.0.0.0", 4000)

    GiByPath["lobby"] = None

    asyncio.get_event_loop().create_task(gameTxQueue(TxQueue))
    registerGameClasses()
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
