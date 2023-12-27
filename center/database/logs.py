import json
from typing import Any, Dict, List, Union, cast
from hexbytes import HexBytes
from mongoengine import *
from web3.types import EventData
from web3 import Web3
from web3.datastructures import AttributeDict
from web3._utils.encoding import FriendlyJsonSerde
from mongoengine.queryset.visitor import Q


class JsonEncoder(json.JSONEncoder):

    def default(self, obj: Any) -> Union[Dict[Any, Any], str]:
        if isinstance(obj, AttributeDict):
            return {k: v for k, v in obj.items()}
        elif isinstance(obj, HexBytes):
            return f"HEXB__{obj.hex()}"
        elif isinstance(obj, bytes):
            return f"BYTE__{obj.hex()}"
        return json.JSONEncoder.default(self, obj)


def to_json(obj: EventData) -> str:
    return FriendlyJsonSerde().json_encode(obj, cls=JsonEncoder)


def from_json(json_str: str) -> EventData:
    event_data = FriendlyJsonSerde().json_decode(json_str)
    for k, v in event_data['args'].items():
        if isinstance(v, str):
            if v.startswith("BYTE__"):
                event_data['args'][k] = bytes.fromhex(v.lstrip("BYTE__"))
            elif v.startswith("HEXB__"):
                event_data['args'][k] = HexBytes(v.lstrip("HEXB__"))
    event_data['blockHash'] = HexBytes(event_data['blockHash'].lstrip("HEXB__"))
    event_data['transactionHash'] = HexBytes(event_data['transactionHash'].lstrip("HEXB__"))
    return cast(EventData, AttributeDict.recursive(event_data))


class EventLog(Document):
    meta = {"collection": "events", "db_alias": "event_logs"}
    id = SequenceField(primary_key=True, db_alias="event_logs")
    blockNumber = IntField(default=0)
    logIndex = IntField(default=0)
    contract = StringField()
    timestamp = IntField(default=0)
    status = IntField(default=0)  #0为未处理事件,1为已处理事件
    sign = StringField()
    event = StringField()


def create_log(timestamp: int, contract_name: str, event: EventData) -> EventLog:
    sign = Web3.keccak(text=f"{event.blockNumber}-{event.transactionHash.hex()}-{event.logIndex}").hex()
    json = to_json(event)
    return EventLog(timestamp=timestamp, blockNumber=event.blockNumber, logIndex=event.logIndex, event=json, sign=sign, contract=contract_name)


def save_logs(logs: List[EventLog]) -> None:
    for log in logs:
        tmp_log = EventLog.objects(sign=log.sign).first()
        if tmp_log is None:
            log.save()

def getLogCount():
    return EventLog.objects().count()


def getLogs(offset: int, size: int) -> List[EventLog]:
    return list(EventLog.objects().order_by("id").skip(offset).limit(size))


def getLogsByBlock(start_block: int, end_block: int) -> List[EventLog]:
    return list(EventLog.objects(Q(blockNumber__gte=start_block) & Q(blockNumber__lte=end_block)).order_by("id"))


def delLogsByBlock(start_block: int) -> None:
    """删除大于指定块号的事件日志
    :param start_block: 指定块
    """
    EventLog.objects(blockNumber__gt=start_block).delete()
