from center.database.models import *
from web3.types import (EventData)
from center.decorator import new_contract
from center.eventhandler.base import getDonut, createId, getUser, getIndex, getHex, getAddress
import json
import sys
import re


def handleInscriptionData(timestamp, event, contracts):
    id = str(event.args.id)
    data = event.args.data
    value = event.args.value
    sender = event.args.sender

    # value = 1000000000000000000
    # sender = "0x742d35Cc6634C0532925a3b844Bc454e4438f44a"

    inscription = Inscription.objects(id=id).first()

    if inscription is not None:
        print('inscritpion exist')
        return

    user = getUser(sender, timestamp)

    inscription = Inscription(id=id)
    inscription.index = int(id)
    inscription.inscription = data
    inscription.value = str(value)
    inscription.owner = user
    inscription.save()

    obj = parseData(data)

    if obj is None:
        return

    try:
        p = obj["p"]
        op = obj["op"]
        tick = obj["tick"]
        if not isinstance(tick, str):
            return
        if not isinstance(op, str):
            return
        if p != "src-20":
            return
        res = re.match("^[a-z0-9A-Z]{1,10}$", tick)
        if res is None:
            return
    except KeyError:
        return

    if op == "deploy":
        print('deploy')
        deployerFeeRatio = 0
        try:
            max = obj["max"]
            lim = obj["lim"]
            fee = obj["fee"]
            deployerFeeRatio = obj['deployerFeeRatio']

            if int(lim) > int(max):
                print("deploy wrong lim")
                return
            int(fee)
            deployerFeeRatio = int(deployerFeeRatio)
        except KeyError:
            print("keyError")
            return
        except ValueError:
            print("ValueError")
            return

        deployer = Account.objects(id=sender).first()
        if deployer is None or deployer.shareSupply == '0':
            print("deploy: deployer has not created cshare")
            return

        if not isinstance(max, str) or not isinstance(lim, str) or not isinstance(fee, str):
            print('deploy: value is not str')
            return

        src20 = Src20.objects(id=tick).first()
        if src20:
            print('deploy: src deployed')
            return

        src20 = Src20(id=tick)
        src20.tick = tick
        src20.max = max
        src20.limit = lim
        src20.fee = fee
        src20.supply = '0'
        src20.holderCount = 0
        src20.index = getIndex('src20')
        src20.isFinished = False
        src20.createAt = timestamp
        src20.deployer = sender
        src20.deployerFeeRatio = deployerFeeRatio
        src20.save()
        return

    if op == "mint":
        print("mint")

        try:
            amt = obj["amt"]
            subject = obj["promoter"]
            subject = getAddress(subject)
            if not subject:
                return
            if not isinstance(amt, str):
                print("mint: amt is not strm")
                return
            int(amt)
        except KeyError:
            print("keyError")
            return
        except ValueError:
            print("ValueError")
            return


        kol = Account.objects(id=subject).first()
        if kol is None or kol.shareSupply == '0':
            print("mint: subject has no cshare")
            return

        src20 = Src20.objects(id=tick).first()
        if src20 is None:
            print('mint: src not deployed')
            return

        if int(src20.max) < (int(src20.supply) + int(amt)):
            print("mint: wrong int number")
            return

        if int(value) < int(src20.fee):
            print("mint: insuffient fee")
            return

        if int(amt) > int(src20.limit):
            print('mint: wrong amount')
            return

        deployer = Account.objects(id=src20.deployer).first()

        src20.supply = str(int(src20.supply) + int(amt))

        deployerFee = int(int(value) * src20.deployerFeeRatio / 10000)
        kolFee = int(value) - deployerFee
        kol.inscriptionFee = str(int(kol.inscriptionFee) + kolFee)
        deployer.deployIncome = str(int(deployer.deployIncome) + deployerFee)

        src20BalanceId = tick + '-' + sender
        src20Balance = Src20Balance.objects(id=src20BalanceId).first()
        if src20Balance is None:
            src20Balance = Src20Balance(id=src20BalanceId)
            src20Balance.tick = tick
            src20Balance.holder = sender
            src20Balance.amount = "0"
            src20.holderCount = src20.holderCount + 1

        if src20.supply == src20.max:
            src20.isFinished = True

        src20Balance.amount = str(int(src20Balance.amount) + int(amt))

        kol.save()
        deployer.save()
        src20Balance.save()
        src20.save()
        return

    if op == "transfer":
        print('transfer')

        src20 = Src20.objects(id=tick).first()
        if src20 is None:
            print("transfer: src20 not deployed")
            return

        try:
            amt = obj["amt"]
            to = obj["to"]
            to = getAddress(to)
            if not to:
                print('transfer: wrong to address')
                return
        except KeyError:
            print("keyError")
            return
        except ValueError:
            print("ValueError")
            return

        toAccount = getUser(to, timestamp)

        fromBalanceId = tick + '-' + sender
        toBalanceId = tick + '-' + to

        fromBalance = Src20Balance.objects(id=fromBalanceId).first()

        if fromBalance is None:
            print("transfer: no balance")
            return

        if int(fromBalance.amount) < int(amt):
            print("transfer: insuffient balance")
            return

        toBalance = Src20Balance.objects(id=toBalanceId).first()
        if toBalance is None:
            toBalance = Src20Balance(id=toBalanceId)
            toBalance.tick = tick
            toBalance.holder = toAccount
            toBalance.amount = '0'
            src20.holderCount += 1

        toBalance.amount = str(int(toBalance.amount) + int(amt))
        fromBalance.amount = str(int(fromBalance.amount) - int(amt))
        if fromBalance.amount == '0':
            src20.holderCount -= 1

        fromBalance.save()
        toBalance.save()
        src20.save()

    print(" ")


def parseData(data):
    try:
        o = json.loads(data)
        return o
    except Exception as e:
        print(e)
        return None
