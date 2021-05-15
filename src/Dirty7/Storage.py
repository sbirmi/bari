import sqlite3

from fwk.Storage import (
        Bool,
        Int,
        Json,
        Table,
        Txt,
)

class Lobby(Table):
    fields = [
        Int("maxGameIdx", qualifier="not null"),
    ]

class RoundParameters(Table):
    fields = [
        Int("paramsId", qualifier="not null"),
        Json("ruleNames"),
        Int("numPlayers"),
        Int("numDecks"),
        Int("numJokers"),
        Int("numCardsToStart"),
        Int("declareMaxPoints"),
        Int("penaltyPoints"),
        Int("stopPoints"),
        Json("scoringSystems"),
        Int("roundNum"),
        Txt("ruleEngine"),
    ]

class Room(Table):
    fields = [
        Txt("path", qualifier="not null"),
        Int("hostParamsId"),
        Int("gameState"),
        Json("winners"),
    ]

class Round(Table):
    fields = [
        Txt("path", qualifier="not null"),
        Int("roundParamsId"), # this has scoringSystem too
        Json("playerNameInTurnOrder"),
        Int("turnIdx"),
        Bool("isRoundOver"),
        Json("deckCards"),
        Json("tableCards"),
        Json("hiddenCards"),
        Json("roundScore"), # scoreByPlayerName
    ]

class Player(Table):
    fields = [
        Txt("path", qualifier="not null"),
        Txt("alias", qualifier="not null"),
        Txt("passwd", qualifier="not null"),
    ]

class PlayerRoundStatus(Table):
    fields = [
        Txt("path", qualifier="not null"),
        Int("roundNum"),
        Txt("alias"),
        Json("handCards"),
    ]

class Storage:
    """Storage helper for all Dirty7 games"""

    def __init__(self, filename):
        self.__filename = filename
        self.__conn = sqlite3.connect(self.__filename)
        self.__cursor = self.__conn.cursor()

        self.__lobbyTbl = Lobby(self.cursor)
        self.__roundParamsTbl = RoundParameters(self.cursor)
        self.__roomTbl = Room(self.cursor)
        self.__roundTbl = Round(self.cursor)
        self.__playerTbl = Player(self.cursor)
        self.__playerRoundStatusTbl = PlayerRoundStatus(self.cursor)

        self.commit()

    @property
    def cursor(self):
        return self.__cursor

    def commit(self):
        self.__conn.commit()
