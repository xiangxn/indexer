from enum import Enum, unique
from mongoengine import *


@unique
class PoolStatus(Enum):
    OPENED = 0
    CLOSED = 1

class Account(Document):
    meta = {"collection": "account"}

    id = StringField(required=True, primary_key=True)
    joinIn = IntField(required=True, default=0)
    index = IntField(required=True, default=0)
    holdersCount = IntField(required=True, default=0)
    holdingsCount = IntField(required=True, default=0)
    shareSupply = StringField(required=True, default='0')
    holdings: ListField(ReferenceField("Holder"))
    holders: ListField(ReferenceField("Holder"))
    feeAmount = StringField(required=True, default='0')
    captureCount = IntField(required=True, default=0)
    totalCaptured = StringField(required=True, default='0')
    donateCount = IntField(required=True, default=0)
    totalDonated = StringField(required=True, default='0')
    receivedDonate = StringField(required=True, default='0')
    inscriptionFee = StringField(required=True, default='0')


class Donut(Document):
    meta = {"collection": "donut"}

    id = StringField(required=True, primary_key=True)
    usersCount = IntField(required=True, default=0)
    totalProtocolFee = StringField(required=True, default='0')
    totalCreateFee = StringField(required=True, default='0')
    buyCount = IntField(required=True, default=0)
    sellCount = IntField(required=True, default=0)
    totalValueCapture = StringField(required=True, default='0')
    totalDonated = StringField(required=True, default='0')
    totalFTCBurned = StringField(required=True, default='0')
    totalInscriptionFee = StringField(required=True, default='0')
    inscriptionFeePercent = IntField(required=True, default=0)


class Holder(Document):
    meta = {"collection": "Holder"}

    id = StringField(required=True, primary_key=True)
    createAt = IntField(required=True, default=0)
    holder = ReferenceField("Account")
    subject = ReferenceField("Account")
    sharesOwned = StringField(required=True, default='0')

class ValueCaptured(Document):
    meta = {"collection": "value_captured"}
    subject = ReferenceField("Account")
    investor = ReferenceField("Account")
    amount = StringField(required=True, default='0')
    index = IntField(required=True, default=0)

class Trade(Document):
    meta = {"collection": "trade"}

    id = StringField(required=True, primary_key=True)
    trader = ReferenceField("Account")
    subject = ReferenceField("Account")
    isBuy = BooleanField(required=True, default=False)
    shareAmount = StringField(required=True, default='0')
    ethAmount = StringField(required=True, default='0')
    protocolEthAmount = StringField(required=True, default='0')
    subjectEthAmount = StringField(required=True, default='0')
    supply = StringField(required=True, default='0')
    index = IntField(required=True, default=0)



class Inscription(Document):
    meta = {"collection": "inscription"}

    id = StringField(required=True, primary_key=True)
    index = IntField(required=True, default=0)
    inscription = StringField()
    value = StringField(required=True, default='0')
    owner = ReferenceField("Account")


class Src20(Document):
    meta = {"collection": "src20"}

    id = StringField(required=True, primary_key=True)
    index = IntField(required=True, default=0)
    tick = StringField(required=True)
    max = StringField(required=True, default='0')
    limit = StringField(required=True, default='0')
    fee = StringField(required=True, default='0')
    supply = StringField(required=True, default='0')
    holderCount = IntField(required=True, default=0)
    isFinished = BooleanField(required=True, default=False)


class Src20Balance(Document):
    meta = {'collection': 'src20_balance'}

    id = StringField(required=True, primary_key=True)
    tick = ReferenceField('Src20')
    holder = ReferenceField('Account')
    amount = StringField(required=True, default = '0')


class Donate(Document):
    meta = {'collection': 'donate'}

    id = StringField(required=True, primary_key=True)
    subject = ReferenceField('Account')
    donator = ReferenceField('Account')
    ethAmount = StringField(required=True, default = '0')
    recCShares = StringField(required=True, default = '0')
    tweetId = IntField(required=True, default = 0)
    round = IntField(equired=True, default = 0)
    index = IntField(equired=True, default = 0)


class Counter(Document):
    meta = {'collection': 'counter'}

    id = StringField(required=True, primary_key=True)
    index = IntField(equired=True, default = 0)