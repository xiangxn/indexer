from center.database.models import *
from web3.types import (EventData)
from center.decorator import new_contract
from center.eventhandler.base import getDonut, createId, getUser, getIndex
import json

def handleInscriptionData(timestamp, event, contracts):
    id = str(event.args.id)
    data = event.args.data
    print('data:', data)
    obj = parseData(data)
    print('data:', obj)
    print(obj.p)


    # value = event.args.value
    # sender = event.args.sender

    # inscription = Inscription.objects(id=id).first()
    # if inscription is not None:
    #     return
    
    # user = getUser(sender, timestamp)

    # inscription = Inscription(id=id)
    # inscription.index = int(id)
    # inscription.inscription = data
    # inscription.value = str(value)
    # inscription.owner = user

def parseData(data):
    try:
        s = str(data, 'utf-8')
        print(2, s)
        o = json.loads(s)
        return o
    except:
        print(sys.exc_info()[0])


def handleFeePercentChanged(timestamp, event, contracts):
    donut = getDonut()
    donut.inscriptionFeePercent = event.args.newPercent
    donut.save()