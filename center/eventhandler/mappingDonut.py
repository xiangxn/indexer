from center.database.models import *
from web3.types import (EventData)
from center.eventhandler.base import getDonut, getUser, createId, getIndex

def handleDonate(timestamp, event: EventData, contracts):
    donator = getUser(event.args.donator, timestamp)
    ethAmount = str(event.args.ethAmount)
    subject = getUser(event.args.subject, timestamp)
    
    subject.receivedDonate = str(int(subject.receivedDonate) + int(ethAmount))
    subject.save()

    donator.donateCount += 1
    donator.totalDonated = str(int(donator.totalDonated) + int(ethAmount))
    donator.save()

    createDonate(timestamp, event, contracts)

    donut = getDonut()
    donut.totalDonated = str(int(donut.totalDonated) + int(ethAmount))
    donut.save()

def handleFTCBurned(timestamp, event, contracts):
    donut = getDonut()
    donut.totalFTCBurned = str(int(donut.totalFTCBurned) + int(event.args.FTCBurned))
    donut.save()


def createDonate(timestamp, event, contracts):
    donatedId = createId(event)
    donate = Donate(id=donatedId)
    index = getIndex('donate')

    donate.index = index
    donate.donator = getUser(event.args.donator, timestamp)
    donate.subject = getUser(event.args.subject, timestamp)
    donate.ethAmount = str(event.args.ethAmount)
    donate.recCShares = str(event.args.recCShares)
    donate.tweetId = str(event.args.tweetId)
    donate.round = event.args.round
    donate.save()
