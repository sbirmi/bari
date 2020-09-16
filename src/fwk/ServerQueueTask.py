import asyncio
from collections import defaultdict


# Queue + task for sending messages to clients asynchronously
ClientTxQueueByWs = {}
ClientTxTaskByWs = {}

def clientTxQueueAdd(ws):
    clientTxQueue = asyncio.Queue()
    ClientTxQueueByWs[ws] = clientTxQueue
    ClientTxTaskByWs[ws] = \
            asyncio.get_event_loop().create_task(
                    clientTxTask(clientTxQueue, ws))

def clientTxQueueRemove(ws):
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


# Queue + tasks to talk between the main loop and the game instances
TxQueue = asyncio.Queue()

def txQueue():
    return TxQueue

GiRxQueueByPath = {}
GiRxTaskByPath = {}

def giRxMsg(path, msg):
    GiRxQueueByPath[path].put_nowait(msg)

# Tracks websockets connected to a given path
WsByPath = defaultdict(set)

def wsPathAdd(ws, path):
    WsByPath[path].add(ws)
    print("WsByPath: add", ws, "path", path)

def wsPathRemove(ws, path):
    WsByPath[path].remove(ws)
    print("WsByPath: remove", ws, "path", path)

# GameInstance by path
GiByPath = {}

def socketsByPath(path):
    return WsByPath.get(path, None)

def giByPath(path):
    return GiByPath.get(path, None)

async def clientTxMsg(ws, msg):
    if ws not in ClientTxQueueByWs:
        print("clientTxMsg: unable to queue",
              "'%s'" % msg,
              "for sending to client", ws)
        return
    print("clientTxMsg:", ws, "'%s'" % msg)
    ClientTxQueueByWs[ws].put_nowait(msg)


def registerGameClass(gi):
    print("Registering {} ({})".format(gi.name, gi.path))

    assert gi.path not in GiByPath
    GiByPath[gi.path] = gi

    giRxQueue = asyncio.Queue()
    gi.setRxTxQueues(giRxQueue, TxQueue)

    GiRxTaskByPath[gi.path] = \
            asyncio.get_event_loop().create_task(gi.worker())

    GiRxQueueByPath[gi.path] = giRxQueue
