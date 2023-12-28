from center.database.models import *
from center.eventhandler.base import getUser, getDonut, getIndex, createId

def handleCreateCshare(timestamp, event, contracts):
    """
    event = {
            'args'
            'event'
            'logIndex'
            'transactionIndex'
            'transactionHash'
            'address'
            'blockHash'
            'blockNumber'
        }
    """
    args = event.args
    subject = args.subject.hex()
    amount = args.amount
    createFee = args.createFee

    donut = getDonut()
    kol = getUser(subject, timestamp)
    kol.shareSupply = str(amount)

    donut.totalCreateFee = str(int(donut.totalCreateFee) + createFee)

    holderId = subject + subject
    holder = Holder.objects(id=holderId).first()
    if holder is None:
        holder = Holder(id=holderId)
        holder.holder = subject
        holder.subject = subject
        holder.createAt = event.blockNumber
    
    holder.sharesOwned = amount
    donut.buyCount = donut.buyCount + 1
    kol.holdingsCount = 1
    kol.holdings = [holder]
    kol.holdersCount = 1
    kol.holders = [holder]

    kol.save()
    holder.save()
    donut.save()

def handleTrade(timestamp, event, contracts):

    args = event.args
    trader = args.trader.hex()
    subject = args.subject.hex()
    isBuy = args.isBuy
    supply = args.supply
    shareAmount = args.shareAmount
    ethAmount = args.ethAmount
    protocolFee = args.protocolEthAmount
    subjectFee = args.subjectEthAmount

    user = getUser(trader, timestamp)
    kol = getUser(subject, timestamp)
    donut = getDonut()

    createTrade(event)

    kol.feeAmount = str(int(kol.feeAmount) + int(subjectFee))
    kol.shareSupply = str(supply)
    holderId = trader + subject
    holder = Holder.objects(id:holderId).first()
    if holder is None:
        holder = Holder(id: holderId)
        holder.holder = trader
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
    holder.save


def handleValueCaptured(timestamp, event, contracts):
    args = event.args
    subject = args.subject.hex()
    investor = args.investor.hex()
    amount = args.amount 

    user = getUser(subject, timestamp)
    user.captureCount += 1
    user.totalCaptured = str(int(user.totalCaptured) + int(amount))
    user.save()

    donut = getDonut()
    donut.totalValueCapture = str(int(donut.totalValueCapture) + int(amount))

    captureId = createId(event)
    capture = ValueCaptured(id: captureId)
    capture.subject = subject
    capture.investor = investor
    capture.amount = str(amount)
    capture.index = getIndex('valueCapture')
    capture.save()


def createTrade(event):
    tradeId = createId(event)
    trade = Trade(id=tradeId)
    trade.index = getIndex('trade')
    trade.trader = event.args.trader.hex()
    trade.subject = event.args.subject.hex()
    trade.isBuy = event.args.isBuy
    trade.shareAmount = event.args.shareAmount
    trade.ethAmount = event.args.ethAmount
    trade.protocolEthAmount = event.args.protocolEthAmount
    trade.subjectEthAmount = event.args.subjectEthAmount
    trade.supply = event.args.supply
    trade.save()