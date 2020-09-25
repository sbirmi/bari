"""Test library for dealing with messages"""

# pylint: disable=missing-class-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=no-self-use

class MsgTestLib:
    def assertGiTxQueueMsgs(self, txq, expectedMsgs):
        """Assert that the full contents of txq is exactly as what is
        provided in expectedMsgs. If expectedMsgs is a list, then the
        order of contents in txq is also asserted.
        Note that txq is drained fully if this verification method passes.

        Arguments
        ---------
        txq : asyncio.Queue
        expectedMsgs : list or set of messages
        """
        foundMsgs = []
        while not txq.empty():
            foundMsgs.append(txq.get_nowait())

        assert len(foundMsgs) == len(expectedMsgs), "Length mismatch: {} != {}".format(
            len(foundMsgs), len(expectedMsgs))

        if isinstance(expectedMsgs, list):
            for i, (found, expected) in enumerate(zip(foundMsgs, expectedMsgs)):
                assert found == expected, "Mismatch at offset {}: {} != {}".format(i, found,
                                                                                   expected)
            assert txq.empty()
        elif isinstance(expectedMsgs, set):
            foundMsgs = set(foundMsgs)
            assert not foundMsgs - expectedMsgs, """Extra messages found:
{}""".format("\n".join(str(msg) for msg in foundMsgs - expectedMsgs))
            assert not expectedMsgs - foundMsgs, """Expected messages missing:
{}""".format("\n".join(str(msg) for msg in expectedMsgs - foundMsgs))
