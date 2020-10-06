bari (बारी)
==========

A web-based, multiplayer turn based game framework and a collection of games.

Requirements
============

1. websockets

   > pip install websockets

2. Flask

   > pip install Flask

Architecture
============

Lobby
-----

Clicking on NEW GAME opens a game specific widget to host a new game. On
hosting a new game, automatically redirect to that game.

    ---------------------------------------------
    Lobby                                        |
    -----                                        |
                                                 |
     [ NEW GAME ]                                |
                                                 |
    Game specific filters:                       |
      [ gamename1      v ]                       |
      [ ] waiting for players                    |
      [ ] ongoing                                |
      [ ] completed                              |
                                                 |
    * game 1 description (game specific widget)  |
    * game 2 description (game specific widget)  |
    * game 3 description (game specific widget)  |
                                                 |
    ---------------------------------------------
       ^
       |
       | single websocket
       |
       v
    ---------------------------------------------
       | | | | | ... (clients)                   |
       | | | | | Client network interface        |
     [ Main loop ]                               |
       | | | |   ... asyncio.Queue (rx, tx)      |
       | | | |                                   |
       | | | +-[ path1 > GameName1:instance1 ]   |
       | | +---[ path2 > GameName1:instance2 ]   |
       | |     ...                               |
       | +-----[ path3 > GameName2:instance1 ]   |
       +-------[ path4 > GameName2:instance2 ]   |
               ...                               |
                                                 |
    ---------------------------------------------


    
       Client1      Client2
        ^            ^
        |            |
      ClientTx     ClientTx
      Queue[ws]    Queue[ws]
        |            |
      [       MainLoop              ]
         ^         |             |
         |         |             |
         |         v             v
      common      RxQueue       RxQueue
      TxQueue     for           for
      for all     game          game
      game        instance.     instance.
      instances.  Element =     Element =
      Element =    (ws, jmsg)    (ws, jmsg)
       (wsOrPath,  |             |
        jmsg)      |             +---> [ game instance 2 ]
                   |
                   +---> [ game instance 1 ]


1. How does a game register the information needed to host a game?
2. How does chat work? What is the scope of chat messages?
3. How does the sender know the handles of everyone in the game?
4. How do folks joining a game send a broadcast to the lobby about users joining?
5. Broadcast messages to just the game?
6. How does the Lobby on hosting a game register queues with the main loop?

1. Need to add version number for lobby, chat lobby + room


Design Invariants
-----------------

1. A game instance once created never gets deleted. Thus its Rx queue alsoi doesn't get deleted even after the game completes.
2. HOST messages should be handled only by the lobby
3. No client should be able to talk to any path other than the one it connected with directly. All internal sinalling
   should be done through the use of InternalXXX messages


Signalling
==========

Errors/Warnings
---------------

1. [ "ERROR", "<explanation>", (optional) original received message ]
2. [ "WARNING", "<explanation>", (optional) original received message ]

Handling new websocket connections
----------------------------------
A new websocket is only allowed to connect to pre-existing paths (such as "/lobby")

1. On connection, notify game instance (for the path) of the websocket appearing
   InternalConnectWsToGi(ws)
2. Each future message from the websocket is put in the game instance's RX queue
3. When the client disconnects, notify game instance (for the path) of the websocket disappearing
   InternalDisconnectWsToGi(ws)


Plugin
======

Handles
-------
1. InternalConnectWsToGi : Main loop --> Plugin
2. InternalDisconnectWsToGi : Main loop --> Plugin

Emits
-----

Handling
--------
1. InternalConnectWsToGi/InternalDisconnectWsToGi
   Tracks the websockets connected to this Plugin instance


Lobby (inherits from Plugin)
============================

1. Accepts requests for hosting a new game
2. Serves the status of each game instance to clients (from a cache)
3. Maintains a cache of game status from each game instance

Additionally Handles
--------------------
1. [ "HOST", "<game-name or path>", details ] : Client --> Lobby
2. InternalGiStatus(fromPath, details) : Game Instance --> Lobby

Emits
-----
1. [ "GAME-STATUS", "<game-instance or path>", details ] : Lobby --> Client

Handling
--------
1. [ "HOST", "<game-name>", details ]
   1. Lobby queues the message InternalHost(path="<game-name>, fromWs, jmsg[2:]) in the TxQueue
   2. Main loop checks if the path is valid. If not, reports bad game name ["HOST-BAD", . Else, queues the InternalHost message to the correct game room

2. InternalGiStatus(fromPath, details)
   1. Maintain a local cache of GAME-STATUS by "<game-instance or path>"
   2. Any changes are broadcasted to all lobby members

3. InternalConnectWsToGi (new client to the Lobby)
   1. Flush all "GAME-STATUS" messages from cache to the client


Game Lobby (inherits from Plugin)
=================================

Additionally Handles
--------------------
1. InternalHost(path="<game-name>", fromWs, details) : Lobby --> Game Lobby

Emits
-----
1. [ "HOST-BAD", "<explanation>", details ] : Game Lobby/Main Loop --> Client
2. InternalRegisterGi(gi) : Game Lobby --> Main Loop
3. InternalGiStatus(fromPath, details)
4. [ "HOST-OKAY", "<game-instance or path>" ] : Game Lobby --> Client

Handling
--------

1. InternalHost(path, fromWs, details)
   1. If details aren't correct, emit HOST-BAD
   2. gi = Create a new game
   3. Emit InternalRegisterGi(gi)
   4. Emit IntenalGiStatus(fromPath, jmsg)
   5. Emit HOST-OKAY to fromWs


Game Instance (inherits from Plugin)
====================================

Additionally Handles
--------------------

Emits
-----
1. InternalGiStatus(fromPath, details)

Handling
--------
1. On TxQueue being set, emit InternalGiStatus
