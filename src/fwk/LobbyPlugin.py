from fwk.GamePlugin import Plugin

class LobbyPlugin(Plugin):
    pass

def plugin():
    return LobbyPlugin("lobby", "Game Lobby")
