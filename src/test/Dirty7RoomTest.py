import unittest
from Dirty7 import Dirty7Round

class Dirty7RoomTest(unittest.TestCase):
    def test1(self):
        rp = Dirty7Round.RoundParameters({"basic"}, 2, 1, 0,
                                         7, 7, 40, 100)
        print(rp.state.numPlayers)
