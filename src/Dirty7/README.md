# Dirty7

TODO Add version #

## Rules


# Messages

Server --> Client
   ["ROUND-PARAMETERS", roundNum <int>, {"numDecks": <int>,
                                          "numJokers": <int>,
                                          "numCardsToStart": <int>,
                                          "declareMaxPoints": <int>,
                                          "penaltyPoints": <int>,
                                          "numStopPoints": <int>}]
   ["ROUND-SCORE", roundNum <int>, {playerName: score, ...}]
   ["PLAYER-CARDS", roundNum <int>, playerName <str>, numCards <int>,
    [card1, card2, ...]]
      - The last element (list of cards) is sent to the connections for
        the correct player in the active round and to all connections
        for completed rounds
      The list of cards is only sent to connections for the actual player.
      Other players receive the same message but without the list of cards
   ["TABLE-CARDS", roundNum <int>,
    numDeckCards <int>,
    numHiddenCards <int>,
    [faceUpCard1, faceUpCard2, ...]]

Client --> Server
   ["JOIN", playerName, passwd, (avatar)]
      ["JOIN-OKAY", playerName]
      ["JOIN-BAD", "reason", (opt) bad-data]

Server --> Client
   ["ROUND-START", roundNum <int>, turnOrder (list of player names), roundParameters]

Server --> Client
   ["TURN", playerName]

Client --> Server
   ["PLAY", {"dropCards": list of cards,
             "numDrawCards": int,
             "pickCards": list of cards}]

      ["PLAY-OKAY"]
      ["PLAY-BAD", "reason", (opt) bad-data]

Server --> Client
   ["ROUND-OVER", roundNum <int>, scoreByPlayerName]

Server --> Client
   ["GAME-OVER", list of winning playerNames]


# Internal state machine

WAITING_FOR_PLAYERS (len(players) < numPlayers)

ROUND_START
   - publish new round information. Move to player turn

PLAYER_TURN (turnIdx)

ROUND_STOP
   - if stop criteria met, go to GAME_OVER
   - start new round (ROUND_START)

GAME_OVER

## RoundParameters

# Game components

## Dirt7Room (Game Instance)
* path
* txQueue messages dispatched to most recent round
* players (dictionary: player.name --> Player)
* scoreCard
* connsToPlayerName
* rounds (list of Dirty7Round)
* hostParameters (HostParameters)
* supportedRuleEngines = {ruleEngineName: RuleEngine}

## Player
* name
* passwd
* playerConns

## MoveProcessor
* round (Dirty7Round)

## RuleEngine
* rxQueue
* moveProcessorList (list of move validation and enactors)
* conns
* round (Dirty7Round)


## HostParameters
* ruleSet = subset from
     {"random",
      "basic",
      "basic-10card",
      "pick-any",
      "seq3",
      "seq3+",
      "declare-any",
      "hearts-1",
      "one-or-seq3",
      "one-or-seq3+",
      "flush4"}
* numPlayers

* numDecks
* numJokers
* numCardsToStart
* declareMaxPoints
* penaltyPoints
* numStopPoints

## Dirty7Round
* roundParameters (RoundParameters)
* roundStatus (RoundStatus)
* ruleEngine (RuleEngine)
* playerRoundStatus
* faceDownPile
* faceUpPile
* roundNum
* ruleEngine
* playerNameInTurnOrder (list of player names)
* turnIdx (int)
* faceUpPile (CardPile)
* faceDownPile (CardPile)
* conns (Conns)
* scoreByPlayerName     (score at the end of a round)

## RoundScore : MsgSrc
* scoreByPlayerName

## RoundParameters
* conns
* ruleEngine
* numDecks
* numJokers
* numCardsToStart
* declareMaxPoints
* penaltyPoints


## Card
* suit (enum)
* rank
* points

## CardGroup
* cards     # list to allow duplicates
* conns        (Conns)     # to notify number of cards in hand
  -> overridable method to decide what to send to all players
* playerConns  (Conns)
  -> overridable method to decide what to send to the specific player connections

### Hand : CardGroup
* send count of cards to all players (conns)
* send hand content to playerConns

### FaceDownPile : CardGroup
* send count of all cards to all players

### FaceUpPile : CardGroup
* showingCards (CardGroup)
* hiddenCards (CardGroup)
* notify showingCards to all players

## PlayerRoundStatus
* hand         (CardGroup)
* conns, playerConns (passed to hand)
