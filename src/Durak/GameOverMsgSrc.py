from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)

class GameOverMsgSrc(MsgSrc):
    """
    ["GAME-OVER"]
    """
    def __init__(self, conns):
        super(GameOverMsgSrc, self).__init__(conns)
        self.setMsgs([Jmai(["GAME-OVER"], None)])
