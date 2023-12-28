from hexbytes import HexBytes
from center.database.models import *
from web3.types import (EventData)


def createId(event: EventData) -> str:
    return "{}-{}".format(event.transactionHash.hex(), event.logIndex)


def getHex(data) -> str:
    if isinstance(data, HexBytes):
        return data.hex()
    elif isinstance(data, bytes):
        return f"0x{data.hex()}"
    elif isinstance(data, int):
        return hex(data)
    elif isinstance(data, str):
        return f"0x{data.encode().hex()}"
    return str(data)


def getIndex(id: str) -> str:
    counter = Counter.objects(id=id).first()
    if counter is None:
        counter = Counter(id=id)
        counter.index = 0
    counter.index = counter.index +  1
    counter.save()
    return counter.index


def getUser(id: str, timestamp: str) -> Account:
    user = Account.objects(id=id).first()
    if user is None:
        user = Account(id=id)
        user.joinIn = timestamp
        user.index = getIndex('user')
        user.holders = []
        user.holdings = []
        donut = getDonutb()
        donut.usersCount = donut.usersCount + 1
        donut.save()
        user.save()
    return user


def getDonutb() -> Donutb:
    donut = Donutb.objects(id='Donutb').first()
    if donut is None:
        donut = Donutb(id='Donutb')
        donut.save()
    return donut


def formatOddString(s: str) -> str:
    return s if len(s) % 2 == 0 else f'0{s}'
