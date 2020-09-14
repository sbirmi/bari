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

1. How does a game register the information needed to host a game?
2. How does chat work? What is the scope of chat messages?
3. How does the sender know the handles of everyone in the game?
4. How do folks joining a game send a broadcast to the lobby about users joining?
5. Broadcast messages to just the game?
6. How does the Lobby on hosting a game register queues with the main loop?

Client network layer

Message Protocol
================

[ "DISCONNECT" ]

Lobby
-----

1. [ <str:"gamename">, "HOST" ] : Client -> Server

2. [ <str:"gamename:<gid>">, "GAME", [ .. game specific details .. ] ] : Server -> Client
   This is sent as a response to the "LIST" command or


Game
----

State machine for the game with handlers for various events.

Game API:
   

