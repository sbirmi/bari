Rules
-----

1. Game is played between >= 1 teams. Each team must have at least 2 players.
2. Players can come and go. Game progresses as long as each player on each team
   hasn't played once.
3. New players are added to the end of each team
4. Team assignment logic: pick yourself while joining with an option of auto (waterfill)
5. Playing a turn
   1. The current player = (next player in the next team) is picked.
   2. A random word (with restricted words) are revealed to
      1.  the current player
      2. all players in all other teams
   3. current player has the option to:
      1. skip/lose the word (in which case, a point is awarded to every other team)
      2. (out of band) play the word, i.e., gives clues
      3. if the current player thinks he got his team to say the word
           - he hits the "score" button
      4. if the others think the player didn't get the word (or misconduct happened)
           - raise an alert. The current player can't score unless he "acknowledges" each alert.
           - The current player will have a choice to lose the word (without having to uncheck alert)
      5. multiple words can appear within the duration of the turn
6. Scoring
7. Pausing the game (future extension)

# UI ideas

Game Room N
```
Host properties
   # of teams [T=1..4]
   Time for each player [30..180 seconds]
   Word sets
      [ ] Kids
      [ ] Wordlist1
      [ ] Wordlist2
```

When a player joins:
```
Game Room: N
Alias: [str]
Team: [0=auto, 1..T]
   auto makes sure that reconnecting players go to the
   correct team
```

---

# Lobby

## Host Parameters (dict)

```
{"numTeams": <int>,         # 1..4
 "turnDurationSec": <int>,  # 30..180
 "wordSets": ["name1", "name2", ...],
 "numTurns": <int>,        # 1..8
}
```

## Room status updates

Server --> Lobby

```
["GAME-STATUS", <path:str>, {"gameState": <str>,    WAITING_FOR_GAME_TO_START, WAITING_FOR_KICKOFF, TURN, GAME_OVER
                             "clientCount": {teamId<int>:{plyrName<str>:clientCount<int>}},
                             "hostParams": <dict>,
                             "winners": [winnerTeam<int>,winnerTeam<int>,...]
                             }
]

"winners" = [] if "gameState" != GAME_OVER else [i.teamNumber for i in winner_team_list]
```

## Game over

Server --> client

```
["GAME-OVER", [winnerTeamId1, winnerTeamId2]]
```

The "winners" key only appears if the game is over

# Game room

## Host parameters

Informs players connected to a game room of the game parameters

Server --> client

```
["HOST-PARAMETERS", host-parameters]
```

## Player join interaction

New players may be allowed to join in the middle of the game if the game isn't over.

Client --> Server

```
["JOIN", playerName:str, team:int={0..T}]   # T = number of teams
   ["JOIN-OKAY", playerName, team:int=t]
   ["JOIN-BAD", "reason", (opt) bad-data]
```

   If the player name is already registered to the game, the team can't be changed
   by rejoining with the same name. The JOIN-OKAY message would override the team
   choice as needed.

## Player status (this isn't specific to a turn)

```
["PLAYER-STATUS", playerName<str>, {"numConns": <int>}]
```

## Team status (this isn't specific to a turn)

Server --> client

```
["TEAM-STATUS", team:int, ["plyr1", "plyr2", ...]]
```

Players are listed in turn order.


## Score (is this needed?)

Server --> client

```
["SCORE", {team<int>: score,
           team<int>: score}]
```

## Turn

Server --> client

When KICKOFF has been received, public-msg sent to everyone for the word then its in in play
```
["TURN",
 turn<int>,
 wordIdx<int>,
 {"team": <int>,
  "player": <str>,
  "state": IN_PLAY,
 }
]
```

When the word is in play, the secret word is shown only to the active player + all members of all other teams
```
["TURN",
 turn<int>,
 wordIdx<int>,
 {"team": <int>,
  "player": <str>,
  "secret": <str>,
  "disallowed": [<str1>, ...],
  "state": IN_PLAY,
 }
]
```

When the word is completed (by discarding or scoring), the secret word + score is shown to all
```
["TURN",
 turn<int>,
 wordIdx<int>,
 {"team": <int>,
  "player": <str>,
  "secret": <str>,
  "disallowed": [<str1>, ...],
  "state": COMPLETED | TIMED_OUT | DISCARDED,
  "score": [teamId1, teamId2, ...],
 }
]
```

## Raising alerts + Claiming a point/Discarding

Client --> server, then server --> all clients

```
["ALERT", turn<int>, wordIdx<int>, {"from": plyrName<str>}]
```

## Claiming a point

Client --> server

```
["COMPLETED", turn<int>, wordIdx<int>]
```

## Discarding

Client --> server

```
["DISCARD", turn<int>, wordIdx<int>]
```


## Game start interaction

All connected players hit the ready button (each team must have at least 2 players).

Client --> start

```
["READY"]
```

## Start turn

When the next player is decided by the TurnManager and the TurnMgr state is WAITING_FOR_KICKOFF

Server --> client

```
["WAIT-FOR-KICKOFF",
 turn<int>,
 "player": <str>,
]
```

When the player is ready, player sends:

Client --> server

```
["KICKOFF"]
```
