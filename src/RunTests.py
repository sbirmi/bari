#!/usr/bin/env python
"""
Run unittests for bari
"""

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import

from test.LobbyPluginTest import *
from test.MsgSrcTest import *
from test.ChatRoomTest import *
from test.Dirty7RoomTest import *

if __name__ == "__main__":
    unittest.main(failfast=True)
