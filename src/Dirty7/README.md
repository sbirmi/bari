# Dirty7

## Rules



# Game components

## Conns
Set of connections
* _msgGens (list of MsgGen)
* addSrc()
   New source: send state to all connections
* delSrc()

* _conns    (set of websockets)
* addConn()
   Walk over each source and serialize its state to the new connection
* delConn()

## MsgGen
* _jmsg
* set()
* get()
* conns (Conns)

## Game

### Start parameters
* path
* numPlayers
* numDecks
* numStopPoints
* numJokers
* numCardsToStart

### Operational status
* players
* turnIdx
* faceUpPile (CardPile)
* faceDownPile (CardPile)
* scoreCard
* conns (all websockets)

## Card
* suit (enum)
* rank

## Hand
* cards     # list to allow duplicates

## Player
* name
* passwd
* ws (set of websockets)
* hand
* score
* myConns (my websockets)
* otherConns (other websockets)

## CardPile
* cards
* conns ()

## ScoreCard
* player x round -> score
