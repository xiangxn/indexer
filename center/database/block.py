from mongoengine import *
from web3.types import BlockData, TxReceipt, EventData, TxData
from center.json import JsonEncoder
from web3._utils.encoding import FriendlyJsonSerde
from typing import Any, Dict, List, Union, cast
from mongoengine.queryset.visitor import Q
from web3.datastructures import AttributeDict
from center.json import json_decode


class EventInfo(object):
    contract: str = None
    timestamp: int = 0
    event: EventData = None
    receipt: TxReceipt
    transaction: TxData


class ReceiptLog(Document):
    meta = { "collection": "receipts", "db_alias": "block_logs"}
    txHash = StringField(primary_key=True, db_alias="block_logs")
    blockNumber = IntField(default=0)
    receipt = StringField()

    def get(self):
        data = json_decode(self.receipt)
        return cast(TxReceipt, AttributeDict.recursive(data))

    @classmethod
    def to_json(cls, obj: TxReceipt):
        return FriendlyJsonSerde().json_encode(obj, cls=JsonEncoder)

    @classmethod
    def create_log(cls, receipt: TxReceipt):
        json = cls.to_json(receipt)
        return cls(txHash=receipt.transactionHash.hex(), blockNumber=receipt.blockNumber, receipt=json)

    @classmethod
    def save_logs(cls, logs: list):
        for log in logs:
            tmp_log = cls.objects(txHash=log.txHash).first()
            if tmp_log is None:
                log.save()


class BlockLog(Document):
    meta = { "collection": "blocks", "db_alias": "block_logs"}
    blockNumber = IntField(primary_key=True, db_alias="block_logs")
    timestamp = IntField(default=0)
    status = IntField(default=0)  #0为未处理块,1为已处理块
    block = StringField()

    def get(self):
        data = json_decode(self.block)
        return cast(BlockData, AttributeDict.recursive(data))

    @classmethod
    def to_json(cls, obj: BlockData):
        return FriendlyJsonSerde().json_encode(obj, cls=JsonEncoder)

    @classmethod
    def create_log(cls, block: BlockData):
        json = cls.to_json(block)
        return cls(timestamp=block.timestamp, blockNumber=block.number, block=json)

    @classmethod
    def save_logs(cls, logs: list):
        for log in logs:
            tmp_log = cls.objects(blockNumber=log.blockNumber).first()
            if tmp_log is None:
                log.save()

    @classmethod
    def getLogCount(cls):
        return cls.objects().count()

    @classmethod
    def getLogs(cls, offset: int, size: int):
        return list(cls.objects().order_by("blockNumber").skip(offset).limit(size))

    @classmethod
    def getLogsByBlock(cls, start_block: int, end_block: int):
        return list(cls.objects(Q(blockNumber__gte=start_block) & Q(blockNumber__lte=end_block)).order_by("blockNumber"))

    @classmethod
    def delLogsByBlock(cls, start_block: int):
        """删除大于指定块号的事件日志
        :param start_block: 指定块
        """
        cls.objects(blockNumber__gt=start_block).delete()
