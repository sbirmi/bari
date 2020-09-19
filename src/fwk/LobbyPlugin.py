from fwk.GamePlugin import Plugin

LOBBY_PATH = "lobby"

class LobbyPlugin(Plugin):
    pass

def plugin():
    return LobbyPlugin(LOBBY_PATH, "Game Lobby")
