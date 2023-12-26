from enum import Enum
import random

from fwk.MsgSrc import (
        Jmai,
        MsgSrc
)

from Common.Card import Card

class RoundState(Enum):
    WAIT_FIRST_ATTACK = 1
    WAIT_DEFENSE_OR_ATTACK = 2
    WAIT_NEXT_ATTACK = 3
    WAIT_NEXT_ATTACK_OR_DEFENSE = 4
    ROUND_OVER = 5

class Round(MsgSrc):
    """
    ["ROUND",
     <roundNum:int>,
     {# If the round is on-going
      playerTurnOrder=[], # list of player names
      attackers=[],       # list of player names
      <defender:str>,     # player name

      # If the round is over
      playerLost=<playerName:str>,
     }]
    """
    def __init__(self, conns,
                 roundNum,
                 roundParameters,
                 playerByName,
                 playerTurnOrder,
                 startTurnIdx=0):
        super(Round, self).__init__(conns)

        self.roundNum = roundNum
        self.roundParameters = roundParameters
        self.playerByName = playerByName
        self.playerTurnOrder = playerTurnOrder
        self.startTurnIdx = startTurnIdx

        self.roundState = RoundState.WAIT_FIRST_ATTACK
        self.attackerIdxs = []
        self.defenderIdx = None
        self.playerLost = None

        # Sets up the table and deals out cards
        self.tableCardsMsgSrc = TableCardsMsgSrc(
                self._conns, roundParameters,
                {pn: player.hand for pn, player in self.playerByName.items()})

        self.startTurn()

    def firstPlayerIdxWithCards(self, idx):
        numPlayers = len(self.playerByName)
        for i in range(idx, idx + numPlayers):
            j = i % numPlayers
            playerName = self.playerTurnOrder[j]
            player = self.playerByName[playerName]
            if player.cardCount() > 0:
                return j

        return None

    def startTurn(self):
        # Assert the round isn't over
        assert self.roundState != RoundState.ROUND_OVER

        self.roundState = RoundState.WAIT_FIRST_ATTACK

        self.attackerIdxs = [self.firstPlayerIdxWithCards(self.startTurnIdx)]
        self.defenderIdx = self.firstPlayerIdxWithCards(self.startTurnIdx + 1)

        assert self.attackerIdxs[0] is not None
        assert self.defenderIdx is not None
        assert self.attackerIdxs[0] != self.defenderIdx

        self.refresh()

    def refresh(self):
        data = {}

        if self.roundState == RoundState.ROUND_OVER:
            data.update({
                "playerLost": self.playerLost,
            })
        else:
            data.update({
                "playerTurnOrder": self.playerTurnOrder,
                "attackers": [self.playerTurnOrder[aidx] for aidx in self.attackerIdxs],
                "defender": self.playerTurnOrder[self.defenderIdx],
            })
        self.setMsgs([
            Jmai(["ROUND", self.roundNum, data], None),
        ])

class TableCardsMsgSrc(MsgSrc):
    """
    ["TABLE-CARDS",
     trumpSuit: str,
     numDrawPileCards : int,  # includes face up card
     bottomCard : [suit, card] or null,
     attackPilesByPlayerName : {"playerName": [
        [card1, ...], # pile 1
        ],
     },
    ]
    """
    def __init__(self,
                 conns,
                 roundParameters,
                 handByPlayerName,
                 numDecks=1,
                 numCardsToStart=6): # PENDING: move some to roundParameters
        assert numDecks >= 1
        super(TableCardsMsgSrc, self).__init__(conns)
        self.roundParameters = roundParameters
        self.handByPlayerName = handByPlayerName

        # Initialize deck. Top of the deck is to the right (-1); bottom
        # to the left (0)
        self.cards = list(Card.deckCards(numDecks=numDecks))
        random.shuffle(self.cards)
        self.trumpSuit = self.cards[0].suit

        self.attackPilesByPlayerName = {}

        self.refresh()

        # Deal deck
        for hand in handByPlayerName.values():
            playerCards = [self.cards.pop() for _ in range(numCardsToStart)]
            hand.setCards(playerCards)

    def refresh(self):
        msg = ["TABLE-CARDS",
               self.trumpSuit,
               len(self.cards),
               self.cards[-1] if self.cards else None,
               {pn: [[card.toJmsg() for card in pile] for pile in attackPiles]
                for pn, attackPiles in self.attackPilesByPlayerName.items()}
              ]
        self.setMsgs([Jmai(msg, None)])
