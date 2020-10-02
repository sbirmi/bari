"""Test library for dealing with messages"""

# pylint: disable=missing-class-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=no-self-use

class MsgTestLib:
    def assertGiTxQueueMsgs(self, txq, expectedMsgs, anyOrder=False):
        """Assert that the full contents of txq is exactly as what is
        provided in expectedMsgs. If expectedMsgs is a list, then the
        order of contents in txq is also asserted.
        Note that txq is drained fully if this verification method passes.

        Arguments
        ---------
        txq : asyncio.Queue
        expectedMsgs : list or set of messages
        """
        assert isinstance(expectedMsgs, list)
        expectedMsgs = expectedMsgs[:]

        i = 0
        while not txq.empty():
            tmsg = txq.get_nowait()

            if anyOrder:
                try:
                    idx = expectedMsgs.index(tmsg)
                except ValueError:
                    raise AssertionError("""Queued message {} not found in expected messages:
{}""".format(tmsg, "\n".join(map(str, expectedMsgs))))

                expectedMsgs.pop(idx)

            else:
                # Order is important
                expectedMsg = expectedMsgs.pop(0)
                assert tmsg == expectedMsg, "Mismatch at offset {}: {} != {}".format(
                    i, tmsg, expectedMsg)
            i += 1

        assert not expectedMsgs, """Some expected messages not found:
{}""".format("\n".join(expectedMsgs))
