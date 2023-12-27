from hexbytes import HexBytes
from center.eventhandler.base import getHex


class TestHex(object):

    def test_hex(self):
        d = getHex(1000)
        print(d)
        assert d == "0x3e8"
        d = getHex("abcde")
        print(d)
        assert d == "0x6162636465"
        d = getHex(HexBytes("7b1941ae388f62d5caf20d4f709aafd74001ff58"))
        print(d)
        assert d == "0x7b1941ae388f62d5caf20d4f709aafd74001ff58"
