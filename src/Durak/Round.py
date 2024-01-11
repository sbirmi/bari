from collections import defaultdict
from enum import Enum
import random

from fwk.Msg import ClientTxMsg
from fwk.MsgSrc import (
        Jmai,
        MsgSrc
)

from Common.Card import (
        Card,
        cardListContains,
)
from Durak.ScoreCardMsgSrc import ScoreCardMsgSrc

class RoundState(Enum):
    WAIT_FIRST_ATTACK = 1
    PAST_FIRST_ATTACK = 2
    DEFENDER_GAVEUP = 3
    ROUND_OVER = 4
    GAME_OVER = 5

class Round(MsgSrc):
    """
    ["ROUND",
     {# If the round is on-going
      playerTurnOrder=[], # list of player names
      attackers=[],       # list of player names
      done=[],            # list of player names
      <defender:str>,     # player name
     }]
    """
    def __init__(self, txQueue, conns,
                 roundParameters,
                 playerByName,
                 playerTurnOrder,
                 roundNum=0,
                 startTurnIdx=0,
                 numCardsToStart=6):
        super(Round, self).__init__(conns)

        self.txQueue = txQueue
        self.roundParameters = roundParameters
        self.playerByName = playerByName
        self.playerTurnOrder = playerTurnOrder
        self.startTurnIdx = startTurnIdx
        self.numCardsToStart = numCardsToStart # Pending: pass via round parameters

        self.roundNum = roundNum
        self.roundState = RoundState.WAIT_FIRST_ATTACK
        self.attackerIdxs = []          # Players that can attack in this turn
        self.donePlayers = set()        # Players who don't want to attack anymore in this turn
        self.defenderIdx = None         # Player who is defending in this turn
        self.noCardsPlayerIdxs = []     # Players with 0 cards left
        self.tableCardsMsgSrc = None
        self.scoreCardMsgSrc = None

    def gameOver(self):
        return self.roundState == RoundState.GAME_OVER

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
        # Create the score card exactly once
        if self.scoreCardMsgSrc is None:
            self.scoreCardMsgSrc = ScoreCardMsgSrc(self._conns, self.playerTurnOrder)

        losers = self.scoreCardMsgSrc.playersReachedScore(self.roundParameters.stopPoints)
        if losers:
            # Game over
            self.roundState = RoundState.GAME_OVER
            self.tableCardsMsgSrc.setGameOver(self.playerByName.values())
            return

        self.roundNum += 1
        self.roundState = RoundState.WAIT_FIRST_ATTACK
        self.attackerIdxs = []
        self.donePlayers = set()
        self.defenderIdx = None
        self.noCardsPlayerIdxs = []

        # Sets up the table and deals out cards
        self.tableCardsMsgSrc = TableCardsMsgSrc(
                self._conns, self.roundParameters,
                {pn: player.hand for pn, player in self.playerByName.items()},
                numCardsToStart=self.numCardsToStart)

        self.startTurn()

    def startTurn(self):
        # Assert the round isn't over
        # assert self.roundState  RoundState.ROUND_OVER # PENDING: should there be an assert here?

        self.roundState = RoundState.WAIT_FIRST_ATTACK

        self.attackerIdxs = [self.firstPlayerIdxWithCards(self.startTurnIdx)]
        self.defenderIdx = self.firstPlayerIdxWithCards(self.startTurnIdx + 1)
        self.donePlayers = set()

        assert self.attackerIdxs[0] is not None
        assert self.defenderIdx is not None
        assert self.attackerIdxs[0] != self.defenderIdx

        self.tableCardsMsgSrc.newTurn()

        self.refresh()

    def maybeTurnOver(self):
        """Returns True if turn/game is over. Otherwise False.

        Turn is over if
        - self.roundState = DEFENDER_GAVEUP
        - all attackes have declared done && defender has defended
        - defender has 0 cards left
        """
        if not (self.roundState == RoundState.DEFENDER_GAVEUP or
                (len(self.attackerIdxs) == len(self.donePlayers) and
                 not self.tableCardsMsgSrc.attackDefendStatus()[1]) or
                self.defenderPlayer().cardCount() == 0):
            # Turn not over yet
            return False

        # When starting a rew round
        # - deal out cards as necessary
        # - figure out noCards players
        # - figure out if game is over
        # - advance turnIdx

        # Deal cards
        for player in self.attackerPlayers() + [self.defenderPlayer()]:
            cardsDeficiet = self.numCardsToStart - player.cardCount()
            cardsDeficiet = cardsDeficiet if cardsDeficiet > 0 else 0

            drawIncomplete = self.tableCardsMsgSrc.playerDraw(player, cardsDeficiet)
            if drawIncomplete:
                # Draw deck is empty
                break

        # Check who has finished
        for player in self.playerByName.values():
            if player.cardCount() == 0:
                self.donePlayers.add(player)

        if self.maybeRoundOver():
            return True

        if self.roundState == RoundState.DEFENDER_GAVEUP:
            self.startTurnIdx = self.firstPlayerIdxWithCards(self.defenderIdx + 1)
        else:
            self.startTurnIdx = self.defenderIdx

        self.startTurn()
        return True

    def maybeRoundOver(self):
        # If no player has cards remaining or only 1 player has
        # cards remaining, this round is over

        cardCountHistogram = defaultdict(set)

        for playerName, player in self.playerByName.items():
            cardCountHistogram[player.cardCount()].add(playerName)

        if len(cardCountHistogram.get(0, {})) == self.roundParameters.numPlayers:
            self.scoreCardMsgSrc.setRoundLosers(self.roundNum, [])
            self.startRound()
            return True

        if len(cardCountHistogram.get(0, {})) == self.roundParameters.numPlayers - 1:
            # One player is left with all remaining cards
            self.scoreCardMsgSrc.setRoundLosers(self.roundNum,
                                                set(self.playerTurnOrder) - cardCountHistogram[0])
            self.startRound()
            return True

        return False

    def refresh(self):
        data = {}

        if self.roundState != RoundState.ROUND_OVER:
            data.update({
                "playerTurnOrder": self.playerTurnOrder,
                "attackers": [self.playerTurnOrder[aidx] for aidx in self.attackerIdxs],
                "done": [player.name for player in self.donePlayers],
                "defender": self.playerTurnOrder[self.defenderIdx],
            })
        self.setMsgs([
            Jmai(["ROUND", self.roundNum, data], None),
        ])

    #--------------------------------------------
    # Attack handling

    def playerAttack(self, ws, attackingPlayer, attackCards):
        if self.roundState in {RoundState.ROUND_OVER, RoundState.DEFENDER_GAVEUP}:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Can't attack right now"],
                                                {ws}, initiatorWs=ws))
            return True

        if attackingPlayer in self.donePlayers:
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-BAD", "Can't attack after declaring done"],
                                                {ws}, initiatorWs=ws))
            return True

        # Defender can't attack if there is nobody left to defend
        defenderPlayer = self.defenderPlayer()
        if (len(self.attackerIdxs) + len(self.noCardsPlayerIdxs) + 1 ==
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

            # PENDING: fold the code so there is one place for attack okay etc
            # Send ATTACK-OKAY
            self.txQueue.put_nowait(ClientTxMsg(["ATTACK-OKAY"], {ws}, initiatorWs=ws))

            self.roundState = RoundState.PAST_FIRST_ATTACK

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
        assert nextDefenderIdx not in self.noCardsPlayerIdxs
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
        self.roundState = RoundState.PAST_FIRST_ATTACK

        if not self.maybeTurnOver():
            # If turn isn't over, do an explicit refresh
            self.refresh()

        return True

    #--------------------------------------------
    # Defend handling

    def playerDefend(self, ws, player, attackDefendCards):
        """
        attackDefendCards = [ [attackCard1, defendCard1], ... ]
        """
        # Ensure round state
        if self.roundState in {RoundState.ROUND_OVER, RoundState.DEFENDER_GAVEUP}:
            self.txQueue.put_nowait(ClientTxMsg(["DEFEND-BAD", "Can't defend right now"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure player == defender
        if player != self.defenderPlayer():
            self.txQueue.put_nowait(ClientTxMsg(["DEFEND-BAD", "Not your turn to defend"],
                                                {ws}, initiatorWs=ws))
            return True

        attackCards = [attackCard for attackCard, _ in attackDefendCards]
        defendCards = [defendCard for _, defendCard in attackDefendCards]

        # Ensure defender has all these cards
        if not player.hand.hasCards(defendCards):
            self.txQueue.put_nowait(ClientTxMsg(["DEFEND-BAD", "You don't have defending cards"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure each attack card is undefended
        _, undefendedCards = self.tableCardsMsgSrc.attackDefendStatus()

        if not cardListContains(undefendedCards, attackCards):
            self.txQueue.put_nowait(ClientTxMsg(
                ["DEFEND-BAD", "Some attacks cards being defended are invalid"],
                 {ws}, initiatorWs=ws))
            return True

        # Ensure each defense is a valid defense
        for attackCard, defendCard in attackDefendCards:
            if attackCard.suit == defendCard.suit:
                if attackCard.rank == 1:
                    # Can't defend against an ace if defense is with same suit
                    self.txQueue.put_nowait(ClientTxMsg(
                        ["DEFEND-BAD", f"Can't defend against {attackCard} with {defendCard}"],
                         {ws}, initiatorWs=ws))
                    return True

                if (defendCard.rank != 1 and defendCard.rank <= attackCard.rank and
                    defendCard.rank <= attackCard.rank):
                    self.txQueue.put_nowait(ClientTxMsg(
                        ["DEFEND-BAD", f"Can't defend against {attackCard} with {defendCard}"],
                         {ws}, initiatorWs=ws))
                    return True

            if defendCard.suit not in {attackCard.suit, self.tableCardsMsgSrc.trumpSuit}:
                self.txQueue.put_nowait(ClientTxMsg(
                    ["DEFEND-BAD",
                     f"Can't defend against {attackCard} with {defendCard} (not trump)"],
                     {ws}, initiatorWs=ws))
                return True

        # Update hand
        self.tableCardsMsgSrc.updateDefend(player, attackDefendCards)

        # Send DEFEND-OKAY
        self.txQueue.put_nowait(ClientTxMsg(["DEFEND-OKAY"], {ws}, initiatorWs=ws))

        if not self.maybeTurnOver():
            # If turn isn't over, do an explicit refresh
            self.refresh()

        return True

    #--------------------------------------------
    # Done handling

    def playerDone(self, ws, player):
        # Ensure round state
        if self.roundState != RoundState.PAST_FIRST_ATTACK:
            self.txQueue.put_nowait(ClientTxMsg(["DONE-BAD", "Attack must start first"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure only attackers can send DONE
        if player not in self.attackerPlayers():
            self.txQueue.put_nowait(ClientTxMsg(["DONE-BAD", "Only attackers can play done"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure DONE can't be sent twice
        if player in self.donePlayers:
            self.txQueue.put_nowait(ClientTxMsg(["DONE-BAD", "Already played done"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure there is at least one attack done
        if not self.tableCardsMsgSrc.attackPilesByPlayerName:
            self.txQueue.put_nowait(ClientTxMsg(
                ["DONE-BAD", "Can't declare DONE without some attack"],
                {ws}, initiatorWs=ws))
            return True

        self.donePlayers.add(player)

        self.txQueue.put_nowait(ClientTxMsg(["DONE-OKAY"], {ws}, initiatorWs=ws))

        if not self.maybeTurnOver():
            # If turn isn't over, do an explicit refresh
            self.refresh()

        return True

    #--------------------------------------------
    # GIVEUP handling

    def playerGiveup(self, ws, player):
        # Ensure round state
        if self.roundState != RoundState.PAST_FIRST_ATTACK:
            self.txQueue.put_nowait(ClientTxMsg(["GIVEUP-BAD", "Attack must start first"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure only defender can give up
        defender = self.defenderPlayer()
        if player != defender:
            self.txQueue.put_nowait(ClientTxMsg(["GIVEUP-BAD", "Only defender can give up"],
                                                {ws}, initiatorWs=ws))
            return True

        # Ensure all attacks aren't defended against
        _, undefendedCards = self.tableCardsMsgSrc.attackDefendStatus()

        if not undefendedCards:
            self.txQueue.put_nowait(ClientTxMsg(
                ["GIVEUP-BAD", "All attacks are defended against. You can't give up"],
                {ws}, initiatorWs=ws))
            return True

        # Do the needful when someone gives up
        self.tableCardsMsgSrc.updateGiveup(defender)

        self.txQueue.put_nowait(ClientTxMsg(["GIVEUP-OKAY"], {ws}, initiatorWs=ws))

        self.roundState = RoundState.DEFENDER_GAVEUP
        assert self.maybeTurnOver() is True
        # An explicit self.refresh() isn't needed because we'll start a new turn
        # (or end the game) as needed.

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

    def newTurn(self):
        self.attackPilesByPlayerName = {}
        self.refresh()

    def playerDraw(self, player, numCards):
        actualDeal = min(numCards, len(self.cards))
        cards = [self.cards.pop() for _ in range(actualDeal)]
        player.hand.addCards(cards)
        self.refresh()
        return actualDeal < numCards

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
        Returns 2-tuple =
            (number of defended attacks,
             pending undefended attacks)
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

    def updateDefend(self, defender, attackDefendCards):
        # Remove cards from defender
        defender.hand.removeCards((defendCard for _, defendCard in attackDefendCards))

        # Update table cards with attacks that are covered
        defendCardsByAttackCard = defaultdict(list)
        for attackCard, defendCard in attackDefendCards:
            defendCardsByAttackCard[attackCard].append(defendCard)

        for attackPiles in self.attackPilesByPlayerName.values():
            for pile in attackPiles:
                if len(pile) == 2:
                    # Already defended
                    continue

                attackCard = pile[0]
                if attackCard not in defendCardsByAttackCard:
                    # This attack wasn't defended against
                    continue

                # This card is now defended against
                defenseCard = defendCardsByAttackCard[attackCard].pop()
                pile.append(defenseCard)

                if not defendCardsByAttackCard[attackCard]:
                    # All defenses are used up
                    del defendCardsByAttackCard[attackCard]

                if not defendCardsByAttackCard:
                    break

            if not defendCardsByAttackCard:
                break

        # Done defending against attacks

        self.refresh()

    def updateGiveup(self, defender):
        # Everything in self.attackPilesByPlayerName is given
        # to the defender

        boardCards = []
        for attackPiles in self.attackPilesByPlayerName.values():
            for pile in attackPiles:
                boardCards.extend(pile)

        defender.hand.addCards(boardCards)
        self.attackPilesByPlayerName = {}

        # Explicit self.refresh() isn't needed because we'll start a
        # new turn

    def setGameOver(self, players):
        for player in players:
            player.hand.resetCards()
        self.trumpSuit = None
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
