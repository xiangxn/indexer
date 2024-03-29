from center.database.models import *
from center.eventhandler.base import getUser, getDonut, getIndex, createId
from center.database.block import EventInfo


# def _transfer(eventInfo: EventInfo, **kv):
#     """这是一个特殊的handler,事件来源是transaction中的to为指定合约地址。
#     触发条件是: 1.mapping中有这个handler; 2.合约被调用。
#     可以根据transaction的数据来处理相关逻辑
#     """
#     print("_transfer:", eventInfo.blockNumber, eventInfo.eventName, eventInfo.index)


def handleCreateIPshare(eventInfo: EventInfo, **kv):
    print("handleCreateIPshare:", eventInfo.blockNumber, eventInfo.eventName, eventInfo.index)
    event = eventInfo.event
    timestamp = eventInfo.timestamp
    args = event.args
    subject = args.subject
    amount = str(args.amount)
    createFee = args.createFee

    donut = getDonut()
    kol = getUser(subject, timestamp)
    kol.shareSupply = amount

    donut.totalCreateFee = str(int(donut.totalCreateFee) + createFee)

    holderId = subject + subject
    subjectUser = getUser(subject, timestamp)
    holder = Holder.objects(id=holderId).first()
    if holder is None:
        holder = Holder(id=holderId)
        holder.holder = subjectUser
        holder.subject = subjectUser
        holder.createAt = timestamp

    holder.sharesOwned = amount
    donut.buyCount = donut.buyCount + 1
    kol.holdingsCount = 1
    kol.update(push__holdings=holder)
    kol.holdersCount = 1
    kol.update(push__holders=holder)

    kol.save()
    holder.save()
    donut.save()


def handleTrade(eventInfo: EventInfo, **kv):
    event = eventInfo.event
    timestamp = eventInfo.timestamp

    args = event.args
    trader = args.trader
    subject = args.subject
    isBuy = args.isBuy
    supply = args.supply
    shareAmount = args.shareAmount
    ethAmount = args.ethAmount
    protocolFee = args.protocolEthAmount
    subjectFee = args.subjectEthAmount

    user = getUser(trader, timestamp)
    kol = getUser(subject, timestamp)
    donut = getDonut()

    createTrade(timestamp, event)

    kol.feeAmount = str(int(kol.feeAmount) + int(subjectFee))
    kol.shareSupply = str(supply)
    holderId = trader + subject
    holder = Holder.objects(id=holderId).first()
    if holder is None:
        holder = Holder(id=holderId)
        holder.holder = user
        holder.subject = kol
        holder.createAt = timestamp

    if isBuy:
        holder.sharesOwned = str(int(holder.sharesOwned) + int(shareAmount))
        donut.buyCount = donut.buyCount + 1
        if holder not in user.holdings:
            user.update(push__holdings=holder)
            user.holdingsCount += 1
        if holder not in kol.holders:
            kol.update(push__holders=holder)
            kol.holdersCount += 1
    else:
        holder.sharesOwned = str(int(holder.sharesOwned) - int(shareAmount))
        donut.sellCount -= 1
        if holder.sharesOwned == '0':
            user.holdingsCount -= 1
            kol.holdersCount -= 1

    donut.totalProtocolFee = str(int(donut.totalProtocolFee) + int(protocolFee))

    donut.save()
    user.save()
    kol.save()
    holder.save()


def handleValueCaptured(eventInfo: EventInfo, **kv):
    event = eventInfo.event
    timestamp = eventInfo.timestamp
    args = event.args
    user = getUser(args.subject, timestamp)
    investor = getUser(args.investor, timestamp)
    amount = args.amount

    user.captureCount += 1
    user.totalCaptured = str(int(user.totalCaptured) + int(amount))
    user.save()

    donut = getDonut()
    donut.totalValueCapture = str(int(donut.totalValueCapture) + int(amount))

    captureId = createId(event)
    capture = ValueCaptured(id=captureId)
    capture.subject = user
    capture.investor = investor
    capture.amount = str(amount)
    capture.index = getIndex('valueCapture')
    capture.save()


def createTrade(timestamp, event):
    tradeId = createId(event)
    trade = Trade(id=tradeId)
    trade.index = getIndex('trade')

    trade.trader = getUser(event.args.trader, timestamp)
    trade.subject = getUser(event.args.subject, timestamp)
    trade.isBuy = event.args.isBuy
    trade.shareAmount = str(event.args.shareAmount)
    trade.ethAmount = str(event.args.ethAmount)
    trade.protocolEthAmount = str(event.args.protocolEthAmount)
    trade.subjectEthAmount = str(event.args.subjectEthAmount)
    trade.supply = str(event.args.supply)
    trade.save()
