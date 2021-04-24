"""HOST-PARAMETERS message generator"""

from fwk.MsgSrc import (
        Jmai,
        MsgSrc,
)

class HostParametersMsgSrc(MsgSrc):
    def __init__(self, conns, hostParameters):
        super(HostParametersMsgSrc, self).__init__(conns)
        self.hostParameters = hostParameters
        self.setMsgs([Jmai(["HOST-PARAMETERS"] + self.hostParameters.toJmsg(), None)])
