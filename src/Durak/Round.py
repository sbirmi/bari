from enum import Enum
import random

from fwk.Msg import ClientTxMsg
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
     {# If the round is on-going
      playerTurnOrder=[], # list of player names
      attackers=[],       # list of player names
      <defender:str>,     # player name
     }]
    """
    def __init__(self, txQueue, conns,
                 roundParameters,
                 playerByName,
                 playerTurnOrder,
                 roundNum=0,
                 startTurnIdx=0):
        super(Round, self).__init__(conns)

        self.txQueue = txQueue
        self.roundParameters = roundParameters
        self.playerByName = playerByName
        self.playerTurnOrder = playerTurnOrder
        self.startTurnIdx = startTurnIdx

        self.roundNum = roundNum
        self.roundState = RoundState.WAIT_FIRST_ATTACK
        self.attackerIdxs = []
        self.defenderIdx = None
        self.finishedPlayerIdxs = []
        self.tableCardsMsgSrc = None

    def getPlayersByIdxs(self, idxs):
        return [self.playerByName[self.playerTurnOrder[idx]]
                for idx in idxs]

    def defenderPlayer(self):
        assert self.defenderIdx is not None
        return self.getPlayersByIdxs([self.defenderIdx])[0]

    def attackerPlayers(self):
        return self.getPlayersByIdxs(self.attackerIdxs)

    def firstPlayerIdxWithCards(self, idx):
        numPlayers = len(self.playerByName)
        for i in range(idx, idx + numPlayers):
            j = i % numPlayers
            playerName = self.playerTurnOrder[j]
            player = self.playerByName[playerName]
            if player.cardCount() > 0:
                return j

        return None

    def startRound(self):
        self.roundNum += 1
        self.roundState = RoundState.WAIT_FIRST_ATTACK
        self.attackerIdxs = []
        self.defenderIdx = None
        self.finishedPlayerIdxs = []

        # Sets up the table and deals out cards
        self.tableCardsMsgSrc = TableCardsMsgSrc(
                self._conns, self.roundParameters,
                {pn: player.hand for pn, player in self.playerByName.items()})

        self.startTurn()

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

        if self.roundState != RoundState.ROUND_OVER:
            data.update({
                "playerTurnOrder": self.playerTurnOrder,
                "attackers": [self.playerTurnOrder[aidx] for aidx in self.attackerIdxs],
                "defender": self.playerTurnOrder[self.defenderIdx],
            })
        self.setMsgs([
            Jmai(["ROUND", self.roundNum, data], None),
        ])

    #--------------------------------------------
    # Attack handling
    def playerAttack(self, ws, attackingPlayer, attackCards):
        if not attackCards:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "No cards specified"],
                                                {ws}, initiatorWs=ws))
            return True

        if self.roundState not in {RoundState.WAIT_FIRST_ATTACK,
                                   RoundState.WAIT_DEFENSE_OR_ATTACK,
                                   RoundState.WAIT_NEXT_ATTACK,
                                   RoundState.WAIT_NEXT_ATTACK_OR_DEFENSE}:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Can't attack right now"],
                                                {ws}, initiatorWs=ws))
            return True

        # Defender can't attack if there is nobody left to defend
        defenderPlayer = self.defenderPlayer()
        if (len(self.attackerIdxs) + len(self.finishedPlayerIdxs) + 1 ==
            self.roundParameters.numPlayers and
            defenderPlayer.name == attackingPlayer.name):
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Last defender can't attack"],
                                                {ws}, initiatorWs=ws))
            return True

        # Verify attacker has these cards
        if not attackingPlayer.hand.hasCards(attackCards):
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "You don't have these cards"],
                                                {ws}, initiatorWs=ws))
            return True

        # Verify these cards can be played (are the same rank) if nothing
        # is on the board or match one of the ranks on the board
        validAttack = self.tableCardsMsgSrc.validAttackCards(attackCards)
        if not validAttack:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Can't attack with these cards"],
                                                {ws}, initiatorWs=ws))
            return True


        # Ensure it's only the existing attacker that can attack
        # or the defender if another candidate defender exists
        attackerPlayers = self.attackerPlayers()
        defendedAttackCount, undefendedCards = self.tableCardsMsgSrc.attackDefendStatus()

        if attackingPlayer in attackerPlayers:
            # Existing attacker is adding more cards
            # Ensure defender has enough cards
            if len(undefendedCards) + len(attackCards) > defenderPlayer.cardCount():
                self.txQueue.put_nowait(ClientTxMsg(
                    ["ATTACK-BAD", "Attacking with more cards than defender has"],
                    {ws}, initiatorWs=ws))
                return True

            self.tableCardsMsgSrc.updateAttack(attackingPlayer, attackCards)

            # Send ATTACK-OKAY
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-OKAY"], {ws}, initiatorWs=ws))

            self.refresh()
            return True

        # Someone is playing out of turn
        if attackingPlayer != defenderPlayer:
            self.txQueue.put_nowait(ClientTxMsg(
                ["ATTACK-BAD", "Attacking out of turn"],
                {ws}, initiatorWs=ws))
            return True

        # Defender is trying to attack to pass defense to next player

        if defendedAttackCount > 0:
            # Can't pass defense to next player
            self.txQueue.put_nowait(ClientTxMsg(
                ["ATTACK-BAD", "Can't pass defense to next player now"],
                {ws}, initiatorWs=ws))
            return True

        # Only one rank must have been used for attacks so far
        if len({card.rank for card in undefendedCards}) > 1:
            self.txQueue.put_nowait(ClientTxMsg(
                ["ATTACK-BAD", "Too late to pass the attack to next player"],
                {ws}, initiatorWs=ws))
            return True

        # Ensure next defender has enough cards to defend with
        nextDefenderIdx = self.firstPlayerIdxWithCards(self.defenderIdx + 1)
        assert nextDefenderIdx is not None
        assert nextDefenderIdx not in self.finishedPlayerIdxs
        assert nextDefenderIdx not in self.attackerIdxs

        nextDefender = self.getPlayersByIdxs([nextDefenderIdx])[0]
        if nextDefender.cardCount() < len(undefendedCards) + len(attackCards):
            self.txQueue.put_nowait(ClientTxMsg(
                ["ATTACK-BAD", "Next player doesn't have enough cards to defend with"],
                {ws}, initiatorWs=ws))
            return True

        # Advance defender
        self.attackerIdxs.append(self.defenderIdx)
        self.defenderIdx = nextDefenderIdx

        # Add the attack
        self.tableCardsMsgSrc.updateAttack(attackingPlayer, attackCards)

        # Send ATTACK-OKAY
        self.txQueue.put_nowait(ClientTxMsg(["ATTACK-OKAY"], {ws}, initiatorWs=ws))

        self.refresh()
        return True

class TableCardsMsgSrc(MsgSrc):
    """
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

    def validAttackCards(self, cards):
        # PENDING: can return error reason as string instead
        attackRanks = {card.rank for card in cards}

        # First attack
        if not self.attackPilesByPlayerName:
            if len(attackRanks) > 1:
                return False

            return True

        # There are some attacks/defense on the board already
        attackDefenseRanks = set()
        for attackPiles in self.attackPilesByPlayerName.values():
            for pile in attackPiles:
                attackDefenseRanks |= {card.rank for card in pile}

        if attackRanks - attackDefenseRanks:
            # Some ranks are used that are not on board
            return False

        return True

    def attackDefendStatus(self):
        """
        If an attack pile has a single card => it's not defended against
        """
        defendedAttackCount = 0
        undefended = []
        for attackPiles in self.attackPilesByPlayerName.values():
            for pile in attackPiles:
                if len(pile) == 1:
                    undefended.append(pile[0])
                else:
                    defendedAttackCount += 1
        return defendedAttackCount, undefended

    def updateAttack(self, attacker, cards):
        # Add cards to attack
        if attacker.name not in self.attackPilesByPlayerName:
            self.attackPilesByPlayerName[attacker.name] = []

        attackPiles = self.attackPilesByPlayerName[attacker.name]
        attackPiles.extend([[card] for card in cards])

        # Remove cards from attacker's hand too
        attacker.hand.removeCards(cards)
        self.refresh()

    def refresh(self):
        msg = ["TABLE-CARDS",
               {"trump": self.trumpSuit,
                "drawPileSize": len(self.cards),
                "bottomCard": self.cards[0].toJmsg() if self.cards else None,
                "attacks": {pn: [[card.toJmsg() for card in pile] for pile in attackPiles]
                            for pn, attackPiles in self.attackPilesByPlayerName.items()}}
              ]
        self.setMsgs([Jmai(msg, None)])
