Rules
-----

1. Game is played between >= 1 teams. Each team must have at least 2 players.
2. Players can come and go. Game progresses as long as each player on each team
   hasn't played once.
3. New players are added to the end of each team
4. Team assignment logic: pick yourself while joining with an option of auto (waterfill)
5. Playing a turn
   a. The current player = (next player in the next team) is picked.
   b. A random word (with restricted words) are revealed to
      i.  the current player
      ii. all players in all other teams
   c. current player has the option to:
      i.   skip/lose the word (in which case, a point is awarded to every other team)
      ii.  (out of band) play the word, i.e., gives clues
      iii. if the current player thinks he got his team to say the word
           - he hits the "score" button
      iv.  if the others think the player didn't get the word (or misconduct happened)
           - raise an alert. The current player can't score unless he "acknowledges" each alert.
           - The current player will have a choice to lose the word (without having to uncheck alert)
      v.   multiple words can appear within the duration of the turn
6. Scoring
   a. 
7. Pausing the game (future extension)

# UI ideas

Game Room N
   Host properties
      # of teams [T=1..4]
      Time for each player [30..180 seconds]
      Word sets
         [ ] Kids
         [ ] Wordlist1
         [ ] Wordlist2

When a player joins:
   Game Room: N
   Alias: [str]
   Team: [0=auto, 1..T]
      auto makes sure that reconnecting players go to the
      correct team

-----

# Lobby

## Host Parameters (dict)

```
{"numTeams": <int>,         # 1..4
 "turnDurationSec": <int>,  # 30..180
 "wordSets": ["name1", "name2", ...],
 "allowLateJoinees": <bool>} 
```

## Room status updates

Server --> client

```
   ["GAME-STATUS", <path:str>, {"gameState": <str>,
                                "clientCount": <str>,
                                "spectatorCount": <int>,
                                "hostParams": <dict>}]
```

# Game room

## Player join interaction

New players may be allowed to join in the middle of the game if the game isn't over. If late joinees are allowed, also allow players to leave the game halfway by pressing a button.

Client --> Server

```
   ["JOIN", playerName, team:int={0..T}]   # T = number of teams
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
   ["TEAM-STATUS",
    {team<int>: ["plyr1", "plyr2", ...],
     team<int>: ["plyr3": ... ],
    }
   ]
```

Players are listed in turn order.


## Score

Server --> client

```
   ["SCORE", {team<int>: score,
              team<int>: score}]
```

## Turn

When the turn has to be played

Server --> client
```
   ["TURN",
    turn<int>,
    wordIdx<int>,
    {"team": <int>,
     "player": <str>,
     "result": IN_PLAY | COMPLETED | DISCARDED | DISCARDED_WITH_ALERTS,
    }
   ]

   ["TURN",
    turn<int>,
    wordIdx<int>,
    {"team": <int>,
     "player": <str>,
     "secret": <str>,
     "disallowed": [<str1>, ...],
     "result": IN_PLAY | COMPLETED | DISCARDED | DISCARDED_WITH_ALERTS,
    }
   ]

   ["TURN",
    turn<int>,
    wordIdx<int>,
    {"team": <int>,
     "player": <str>,
     "secret": <str>,
     "disallowed": [<str1>, ...],
     "result": IN_PLAY | COMPLETED | DISCARDED | DISCARDED_WITH_ALERTS,
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
   ["START"]
```


## Game end

Server --> client

```
   ["GAME-OVER", [winnerTeam<int>, winnerTeam<int>, ...]]
```