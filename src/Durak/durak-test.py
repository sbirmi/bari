#!/usr/bin/env python3

import asyncio
import json
import time
import websockets

async def send(uri, msgs):
    async with websockets.connect(uri) as ws:
        for msg in msgs:
            await ws.send(json.dumps(msg))

        start_time = time.time()
        while time.time() - start_time < 0.5:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=0.5)
                print(f"rx {resp}")
            except asyncio.TimeoutError:
                break

async def main():
    uri1 = "ws://localhost:7000/lobby"
    uri2 = "ws://localhost:7000/durak:1"

    await send(uri1, [
        ["HOST", "durak", {"numPlayers": 2, "stopPoints": 1}],
    ])

    await send(uri2, [
        ["JOIN", "sb1"],
    ])

    await send(uri2, [
        ["JOIN", "sb2"],
    ])

    await send(uri2, [
        ["JOIN", "sb1"],
#        ["ATTACK", [["H", 1]]],
    ])

    await send(uri2, [
        ["JOIN", "sb3"],
    ])

asyncio.run(main())
