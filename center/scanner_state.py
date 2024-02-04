import json
import os
import time
from typing import Callable, List, Optional
from center.base_scanner_state import BaseScannerState
import mongoengine
from center.events import Events
from center.logger import Logger
from center.database.logs import delLogsByBlock
from center.database.block import BlockLog, EventInfo
from web3.types import TxData


class ScannerState(BaseScannerState):
    """存储扫描块的状态和所有事件"""

    def __init__(self, config, events: Events, logger: Logger = None) -> None:
        super().__init__()
        self.logger = logger
        self.events = events
        # 运行时不要手动删除此文件，会导致完全重扫
        self.cache_file = "cache-state.json"
        # 多少秒前保存了状态缓存文件
        self.last_save = 0
        self.state = None
        self.config = config['sync_cfg']
        self.db_config = config['mongo']
        self.contracts_config = config['contracts']
        self._init_db()

    def _init_db(self):
        """连接mongoengine"""
        self.db_data = mongoengine.connect(db=self.db_config['db'], host=self.db_config['host'])
        self.db_logs = mongoengine.connect(db=self.db_config['log'], host=self.db_config['host'], alias="block_logs")

    def reset(self):
        """重设无扫描的初始状态"""
        addr = {}
        for k, v in self.contracts_config.items():
            addr[k] = [v]
        self.state = { "last_scanned_block": self.config['start_block'] - 1, "address": addr }
        # self.state = {"last_scanned_block": 0}

    def restore(self):
        """从文件恢复上次扫描状态"""
        try:
            self.state = json.load(open(self.cache_file, "rt"))
            self.logger.warning(f"Restored the state, previously {self.state['last_scanned_block']} blocks have been scanned")
        except (IOError, json.decoder.JSONDecodeError):
            self.logger.exception("State starting from scratch")
            self.reset()

    def save(self):
        """将到目前为止扫描的状态保存在缓存文件中"""
        with open(self.cache_file, "wt") as f:
            json.dump(self.state, f)
        self.last_save = time.time()

    def cleanCache(self):
        """清除缓存状态文件"""
        path = self.cache_file
        if os.path.exists(path):
            os.remove(path)

    def dropLogs(self):
        """从数据库中删除所有事件日志"""
        self.db_logs.drop_database(self.db_config['log'])

    def deleteLogs(self, block: int):
        """清除指定块后的所有事件日志"""
        delLogsByBlock(block)

    def dropData(self):
        """从数据库中删除所有已经生成的数据"""
        self.db_data.drop_database(self.db_config['db'])

    #
    # 下面实现的 EventScannerState 方法
    #

    def add_address(self, contract: str, address: str = None):
        """添加新的要跟踪的合约地址"""
        # TODO: 可以保存到数据中
        if contract and address:
            if contract not in self.state['address'].keys():
                self.state['address'][contract] = [address]
            else:
                self.state['address'][contract].append(address)
                self.state['address'][contract] = list(set(self.state['address'][contract]))
            self.save()

    def get_address(self, contract: str):
        """返回动态跟踪的合约地址"""
        if contract not in self.state['address'].keys():
            return []
        return list(self.state['address'][contract])

    def get_last_scanned_block(self):
        """存储的最后一个块的编号"""
        return self.state["last_scanned_block"]

    def delete_data(self, since_block):
        """从扫描数据中删除可能重组的块"""
        # 通过事件状态更新数据库
        pass

    def start_chunk(self, block_number):
        pass

    def end_chunk(self, block_number):
        """保存在每个块的末尾，这样可以在崩溃或 CTRL+C 的情况下恢复"""
        # 下次启动扫描时，将从该块恢复
        self.state["last_scanned_block"] = block_number

        # 每分钟保存一次缓存文件
        if time.time() - self.last_save > 60:
            self.save()

    def save_blocks(self, blocks: List[BlockLog]):
        """记录块到本地数据库,可以从本地数据重建数据"""
        BlockLog.save_logs(blocks)

    def process_transaction(self, block: TxData):
        # TODO
        pass

    def process_event(self, eventLog: EventInfo, contracts: dict = None, new_contract_address: Optional[Callable] = None) -> None:
        """在事件处理器插件根据事件生成地本数据"""
        block_when = eventLog.timestamp
        contract = eventLog.contract
        event = eventLog.event

        # print("process_event contract:", contract, event.event)

        def check_create_contract(contract_name=None, contract_address=None):
            if contract_name and contract_address:
                if new_contract_address:
                    new_contract_address(contract_name, contract_address)
            return False    # 如果返回True将不会调用handle

        # 调用事件处理器插件处理
        self.events.callHandle(contract, event, block_when, contracts, check_create_contract)
