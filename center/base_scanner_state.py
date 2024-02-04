from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable
from center.database.logs import EventLog
from center.database.block import BlockLog, EventInfo
from web3.types import TxData


class BaseScannerState(ABC):
    """应用程序状态，会记住在崩溃的情况下扫描了哪些块。
    """

    @abstractmethod
    def get_last_scanned_block(self) -> int:
        """在上一个周期扫描的最后一个块的编号。
        :return: 如果还没有扫描到块，则为 0
        """

    @abstractmethod
    def start_chunk(self, block_number: int):
        """将通过 JSON-RPC 轮询多个块的数据。
        如果需要，启动数据库会话。
        """

    @abstractmethod
    def end_chunk(self, block_number: int):
        """扫描已完成了一些块。
        现在保留您所在州的所有数据。
        """

    @abstractmethod
    def save_blocks(self, blocks: List[BlockLog]):
        """预存储块数据到本地数据库"""

    @abstractmethod
    def process_transaction(self, transaction_hash):
        """处理传入的交易,从RPC拉取Receipt"""

    @abstractmethod
    def process_event(self, eventLog: EventInfo, contracts: dict = None, new_contract_address: Optional[Callable] = None) -> None:
        """处理传入事件。
        此函数从 Web3 获取原始事件，将它们转换为您的应用程序内部格式，然后将它们保存在数据库或其他状态中。
        :param eventLog: 事件日志数据
        :param contracts: 配置的固定合约dict
        """

    @abstractmethod
    def delete_data(self, since_block: int) -> int:
        """删除自扫描此块以来的所有数据。
        清除任何潜在的次要重组数据。
        """

    @abstractmethod
    def add_address(self, contract: str, address: str) -> None:
        """添加新的要跟踪的合约地址"""

    @abstractmethod
    def get_address(self, contract: str) -> list:
        """返回动态跟踪的合约地址"""
