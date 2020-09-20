"""Server's internals. Creates and manages various queues in the game.
"""

import asyncio
from collections import defaultdict


# -------------------------------------
# Queue + task for sending messages to
# clients asynchronously

ClientTxQueueByWs = {}
ClientTxTaskByWs = {}

def clientTxQueueAdd(ws):
    """Add a TX queue + task for a websocket"""
    clientTxQueue = asyncio.Queue()
    ClientTxQueueByWs[ws] = clientTxQueue
    ClientTxTaskByWs[ws] = asyncio.get_event_loop().create_task(clientTxTask(clientTxQueue, ws))

def clientTxQueueRemove(ws):
    """Remove a TX queue + task for a websocket"""
    del ClientTxQueueByWs[ws]
    ClientTxTaskByWs[ws].cancel()
    #await asyncio.gather(ClientTxTaskByWs[ws]) # When is this called?
    del ClientTxTaskByWs[ws]

    # Client disconnected
    print("Client", ws, "disconnected")

async def clientTxTask(queue, clientWs):
    """
    Task to drain the queue with messages meant to be
    sent to the client's websocket.
    """
    while True:
        msg = await queue.get()
        print("clientTxTask: sending", "'%s'" % msg, "to", clientWs)
        await clientWs.send(msg)
        queue.task_done()

# -------------------------------------
# Queue + tasks to talk between the
# main loop and the game instances

TxQueue = asyncio.Queue()

def txQueue():
    """Returns the common TX queue used by each Plugin"""
    return TxQueue

GiRxQueueByPath = {}
GiRxTaskByPath = {}

def giRxMsg(path, msg): # pylint: disable=missing-function-docstring
    GiRxQueueByPath[path].put_nowait(msg)

# -------------------------------------
# Tracks websockets connected to a
# given path

WsByPath = defaultdict(set)

def wsPathAdd(ws, path): # pylint: disable=missing-function-docstring
    WsByPath[path].add(ws)
    print("WsByPath: add", ws, "path", path)

def wsPathRemove(ws, path): # pylint: disable=missing-function-docstring
    WsByPath[path].remove(ws)
    print("WsByPath: remove", ws, "path", path)

def socketsByPath(path): # pylint: disable=missing-function-docstring
    return WsByPath.get(path, None)

# -------------------------------------
# GameInstance by path

GiByPath = {}

def giByPath(path):
    """Return game instance for a path. Returns None if
    path is not recognized"""
    return GiByPath.get(path, None)

async def clientTxMsg(msg, toWs):
    """Helper to queue a message to be sent to 'toWs'"""
    if toWs not in ClientTxQueueByWs:
        print("clientTxMsg: unable to queue",
              "'%s'" % msg,
              "for sending to client", toWs)
        return
    print("clientTxMsg:", toWs, "'%s'" % msg)
    ClientTxQueueByWs[toWs].put_nowait(msg)

# -------------------------------------
# Register a game instance with the
# main loop

def registerGameClass(gi):
    """Register game instance with the main loop"""
    print("Registering {} ({})".format(gi.name, gi.path))

    assert gi.path not in GiByPath
    GiByPath[gi.path] = gi

    giRxQueue = asyncio.Queue()
    gi.setRxTxQueues(giRxQueue, TxQueue)

    GiRxTaskByPath[gi.path] = \
            asyncio.get_event_loop().create_task(gi.worker())

    GiRxQueueByPath[gi.path] = giRxQueue
