bari (बारी )
===========

A web-based, multiplayer turn based game framework and a collection of games.

Architecture
============

Lobby
-----

Clicking on NEW GAME opens a game specific widget to host a new game. On
hosting a new game, automatically redirect to that game.

>
> ---------------------------------------------
> Lobby                                        |
> -----                                        |
>                                              |
>  [ NEW GAME ]                                |
>                                              |
> Game specific filters:                       |
>   [ gamename1      v ]                       |
>   [ ] waiting for players                    |
>   [ ] ongoing                                |
>   [ ] completed                              |
>                                              |
> * game 1 description (game specific widget)  |
> * game 2 description (game specific widget)  |
> * game 3 description (game specific widget)  |
>                                              |
> ---------------------------------------------
>    ^
>    |
>    | single websocket
>    |
>    v
> ---------------------------------------------
>    | | | | | ... (clients)                   |
>    | | | | | Client network interface        |
>  [ Main loop ]                               |
>    | | | |                                   |
>    | | | |                                   |
>    | | | +-[ GameName1:instance1 ]           |
>    | | +---[ GameName1:instance2 ]           |
>    | |     ...                               |
>    | +-----[ GameName2:instance1 ]           |
>    +-------[ GameName2:instance2 ]           |
>            ...                               |
>                                              |
> ---------------------------------------------
>

How does chat work?
What is the scope of chat messages?

Client network layer

Message Protocol
================

Lobby
-----

1. [ "LIST" ] : Client -> Server

2. [ "GAME", <str:gamename>, <int:gid>, [ .. game specific details .. ] ] : Server -> Client
   This is sent as a response to the "LIST" command or


Game
----

State machine for the game with handlers for various events.

Game API:
   



