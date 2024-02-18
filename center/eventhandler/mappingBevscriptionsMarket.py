from center.database.models import *
from center.database.block import EventInfo
from center.decorator import new_contract
from center.eventhandler.base import getDonut, createId, getUser, getIndex, getHex, getAddress, hexStrToString
import json
import sys
import re

MarketContract = '0x3550133fFFCAC85F880E159702Be0E4a7049b532'
BatchPurchaseContract = '0xBc3E40fe9e069108dd9B86F6d10130910D760f65'

# test net
# MarketContract = '0xcEB135147D213B671e39EF6dC188661fb7d86e14'
# BatchPurchaseContract = '0x28c06d07559e79b020816c57d4302A701dac7440'

def _transfer(eventInfo: EventInfo, **kv):
    """这里只处理用户的list操作
        即用户发送transfer交易，附带inputdata，用户list铭文
        其他的操作均在事件处理handler中处理
    """
    transaction = eventInfo.transaction
    hash = transaction.hash.hex()
    user = transaction['from']
    marketContract = transaction.to
    data = getHex(transaction.input)

    listTransaction = ListTransaction.objects(id=hash).first()

    # 如果用户已经有一个有效的pending中的list，则新的list无效
    # userPendingList = ListTransaction.objects(user=user, isValid=True, status=0)
    # if len(userPendingList) > 0:
    #     return

    # Market contract as a holder
    dex = getUser(marketContract, eventInfo.timestamp)

    # the transaction is handled
    if listTransaction is not None:
        return

    listTransaction = ListTransaction(id=hash)
    listTransaction.user = user
    listTransaction.save()

    if len(data) < 3:
        return

    data = hexStrToString(data)

    # must start with 'data:application/json,'
    if not data.startswith('data:application/json,'):
        return

    insData = data.replace('data:application/json,', "", 1)

    # parse inscription object
    obj = parseData(insData)

    if obj is None:
        return

    p = obj['p']
    op = obj['op']
    tick = obj['tick']
    amt = obj['amt']

    if (p != 'src-20') or (op != 'list'):
        return

    src20 = Src20.objects(id=tick).first()
    if src20 is None:
        return False

    # transfer inscription
    result = transferInscription(tick, user, marketContract, amt)
    if result is False:
        return

    listTransaction.isValid = True
    listTransaction.tick = tick
    listTransaction.src20 = src20
    listTransaction.amount = amt
    listTransaction.save()


def handleprotocol_TransferBM20TokenForListing(eventInfo: EventInfo, **kv):
    event = eventInfo.event
    f = event.args['from']
    to = event.args.to
    listHash = '0x' + event.args.listId.hex()

    transaction = eventInfo.transaction
    finishedHash = transaction.hash.hex()
    orignalCaller = transaction['from']

    listTransaction = ListTransaction.objects(id=listHash).first()

    if listTransaction is None:
        return

    if not listTransaction.isValid:
        return

    # cancel
    if f == to:
        # transfer inscripton back
        result = transferInscription(listTransaction.tick, MarketContract, to, listTransaction.amount)
        if result:
            listTransaction.status = 2  # 0: pending, 1: deal, 2: cancel
            listTransaction.save()
        return

    # deal
    if to == BatchPurchaseContract:
        # 批量购买的
        result = transferInscription(listTransaction.tick, MarketContract, orignalCaller, listTransaction.amount)
        listTransaction.buyer = orignalCaller
    else:
        # 用户购买的
        result = transferInscription(listTransaction.tick, MarketContract, to, listTransaction.amount)
        listTransaction.buyer = to

    listTransaction.finishedHash = finishedHash
    listTransaction.status = 1
    listTransaction.save()


def parseData(data):
    try:
        o = json.loads(data)
        return o
    except Exception as e:
        print(e)
        return None


def transferInscription(tick, _from, to, amount):
    fromId = tick + '-' + _from
    toId = tick + '-' + to

    src20 = Src20.objects(id=tick).first()
    if src20 is None:
        return False

    fromBalance = Src20Balance.objects(id=fromId).first()
    toBalance = Src20Balance.objects(id=toId).first()

    try:
        if (fromBalance is None) or (int(fromBalance.amount) < int(amount)):
            return False
    except Exception as e:
        print(e)
        return False

    if toBalance is None:
        toBalance = Src20Balance(id=toId)
        toBalance.tick = tick
        toBalance.holder = MarketContract
        toBalance.amount == "0"

    if toBalance.amount == "0":
        src20.holderCount = src20.holderCount + 1

    # update balance
    fromBalance.amount = str(int(fromBalance.amount) - int(amount))
    toBalance.amount = str(int(toBalance.amount) + int(amount))

    if fromBalance.amount == "0":
        src20.holderCount = src20.holderCount - 1

    fromBalance.save()
    toBalance.save()
    src20.save()
    return True
