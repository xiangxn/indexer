from center.database.models import *
from web3.types import (EventData)
from center.decorator import new_contract
from center.eventhandler.base import getDonut, createId, getUser, getIndex, getHex
import json
import sys
import re

def handleInscriptionData(timestamp, event, contracts):
    id = str(event.args.id)
    data = getHex(event.args.data)
    value = event.args.value
    sender = event.args.sender

    inscription = Inscription.objects(id=id).first()
    if inscription is not None:
        return
    
    user = getUser(sender, timestamp)

    inscription = Inscription(id=id)
    inscription.index = int(id)
    inscription.inscription = data
    inscription.value = str(value)
    inscription.owner = user
    inscription.save()

    # slice start "0x"
    data = data[2:]

    print('data:', data)
    obj = parseData(data)
    if obj is None:
        if len(data) <= 40:
            return
        subject = '0x' + data[:40]
        data = data[40:]
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
        try:
            max = data["max"]
            lim = data["lim"]
            fee = data["fee"]

            if int(lim) > int(max):
                return
            int(fee)
        except KeyError:
            return
        except ValueError:
            return
        
        if not isinstance(max, str) or not isinstance(lim, str) or not isinstance(fee, str):
            return
        
        src20 = Src20.objects(id=tick).first()
        if src20:
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
        src20.save()
        return

    if op == "mint":
        kol = Account.objects(id=subject).first()
        if kol is None or kol.shareSupply == '0':
            return
        
        try:
            amt = obj["amt"]
            if not isinstance(amt, str):
                return
            int(amt)
        except ValueError:
            return
        except KeyError:
            return
        
        src20 = Src20.objects(id=tick).first()
        if src20 is None:
            return
        
        if int(src20.max) < (int(src20.supply) + int(amt)):
            return
        
        if int(value) < int(src20.fee):
            return
        
        if int(amt) > int(src20.limit):
            return

        src20.supply = str(int(src20.supply) + int(amt))

        donut = getDonut()
        donutFee = int(int(value) * donut.inscriptionFeePercent / 10000)
        kolFee = int(value) - donutFee
        kol.inscriptionFee = str(int(kol.inscriptionFee) + kolFee)
        donut.totalInscriptionFee = str(int(donut.totalInscriptionFee) + donutFee)

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

        src20Balance.amount = str(int(src20Balance.amount) + amt)

        kol.save()
        donut.save()
        src20Balance.save()
        src20.save()
        return

    if op == "transfer":
        pass
    

def parseData(data):
    try:
        s = bytes.fromhex(data).encoding('utf-8')
        print("hex to string:", s)
        o = json.loads(s)
        return o
    except Exception as e:
        print(e)
        return None


def handleFeePercentChanged(timestamp, event, contracts):
    donut = getDonut()
    donut.inscriptionFeePercent = event.args.newPercent
    donut.save()

