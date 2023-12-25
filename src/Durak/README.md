# Durak

---

# Messages

## Lobby

Client --> server
```
["HOST",
 "durak",
 {"numPlayers": <int>,
  "stopPoints": <int>},
]
```

## Room

Client --> server
```
["JOIN", <playername>]
   ["JOIN-OKAY", playerName]
   ["JOIN-BAD", "reason", (opt) bad-data]
```
---

# Host parameters

1. Number of players: 2..6
2. numDecks = 1
3. numJokers = 0
4. Stop criteria (first to lose N rounds) = 5
5. Trump { "random" }

# Messages

Server --> Client
    When waiting for players
        ["GAME-STATUS", <path:str>, {}]




# Game components

## DurakRoom (Game Instance)
* path
* txQueue
* players: player.name --> Player
* connsToPlayerName
* rounds (list of DurakRoom)
* hostParameters (HostParameters)

## Player
* name
* passwd
* playerConns

## HostParameters = RoundParameters
* numPlayers
* numDecks = 1
* numJokers = 0
* numCardsToStart = 6

## Round
* roundNum
* roundParameters (RoundParameters)
* roundStatus (RoundStatus)
* ruleEngine (RuleEngine)
* playerRoundStatus
* faceDownPile (CardPile)
* attackPiles (CardPile)
* playerNameInTurnOrder (list of player names)
* attackers: list of Players (in the order they are seated)
* defender: Player
* conns (Conns)

## Card
* suit (enum)
* rank
* defendsAginst : (card, trump) --> bool

## CardGroup
* cards             # list to allow duplicates
* conns   (Conns)   # to notify number of cards
* ownerCards (Conns) # reveal all cards to this group

### Hand : CardGroup
* send count of cards to all players
* send hand content to playerConns

### FaceDownPile : CardGroup
* send count to all players

### AttackPiles
* attacks : list of CardGroup
* revealed to everyone
