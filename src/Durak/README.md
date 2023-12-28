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

Server --> client

```
    ["ROUND",
     {# If the round is on-going
      playerTurnOrder=[], # list of player names
      attackers=[],       # list of player names
      <defender:str>,     # player name

      # If the round is over
      playerLost=<playerName:str>,
     }]

    ["TABLE-CARDS",
     {"trump": str,
      "drawPileSize": int, # includes face up card
      "bottomCard": [suit, card] or null,
      "attacks": {"playerName": [
        [card1, ...], # pile 1
        ],
        ...
     },
    ]

    ["PLAYER-HAND", name, numCards, cards (optional)]

    ["PLAYER-STATUS", self.name, self.numConns()]
    
```

Client --> server
```
    ["ATTACK", [ attackCard1, attackCard2, ... ]]

        ["ATTACK-OKAY"]
        ["ATTACK-BAD", reason:str]

    ["DEFEND", [[attackCard1, defendCard1], ... ]]

        ["DEFEND-OKAY"]
        ["DEFEND-BAD", reason:str]

    ["DONE"]

        ["DONE-OKAY"]
        ["DONE-BAD", reason:str]

```


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
