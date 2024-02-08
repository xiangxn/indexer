import asyncio
import time
from typing import List, Tuple, Optional, Callable
from web3 import AsyncWeb3
from web3.exceptions import BlockNotFound
from web3.types import EventData
from web3.datastructures import AttributeDict
from web3._utils.filters import construct_event_filter_params
from web3._utils.events import get_event_data
from center.events import Events, TRANSFER_EVENT_NAME
from center.database.logs import getLogs
from center.base_scanner_state import BaseScannerState
from center.logger import Logger
from center.database.block import BlockLog, ReceiptLog, EventInfo
from center.utils import async_retry
from aiohttp import ClientResponseError


class BlockScanner:
    """扫描区块链中的事件并尽量不要过度滥用 JSON-RPC API。

    可用于实时扫描，因为它检测到较小的链重组和重新扫描。
    与简单的 web3.contract.Contract 不同，此扫描器可以一次扫描来自多个合约的事件。
    例如，您可以在同一次扫描中从所有代币中获取所有转账。

    您*应该*禁用 Web3 提供程序上的默认 `http_retry_request_middleware`，
    因为它无法正确限制和减少 `eth_getLogs` 块编号范围。
    """

    def __init__(self,
                 web3: AsyncWeb3,
                 state: BaseScannerState,
                 events: Events,
                 max_chunk_scan_size: int = 10,
                 request_interval_sec: float = 0.5,
                 request_retry_seconds: float = 3.0,
                 contracts: dict = dict(),
                 logger: Logger = None,
                 switch_provider_handle=None):
        """
        :param web3: 异步Web3对象
        :param state: 扫描的状态管理对象
        :param events: 扫描的 web3 Event 管理对象
        :param filters: 传递给 get_logs 的过滤器
        :param max_chunk_scan_size: 单次并发JSON-RPC请求数量
        :param request_interval_sec: 每次JSON-RPC的间隔
        :param request_retry_seconds: 失败请求之间的延迟,让 JSON-RPC 服务器恢复
        :param contracts: 配置文件中配置的合约map
        :param logger: 日志对象
        :param switch_provider_handle: 切换web3 api的回调
        """
        self.IS_RUN = False
        self.logger = logger
        self.web3 = web3
        self.state = state
        self.events = events
        self.contracts = contracts
        self.switch_provider_handle = switch_provider_handle

        # JSON-RPC 节流参数
        self.min_scan_chunk_size = 10  # 12秒/块 = 120秒周期
        self.max_scan_chunk_size = max_chunk_scan_size
        self.request_retry_seconds = request_retry_seconds
        self.request_interval_sec = request_interval_sec

        # 如果找到结果，考虑增加块大小的速度（开始获得命中后减慢扫描速度）
        self.chunk_size_decrease = 0.5

        # 如果没有找到结果，考虑如何增加块大小
        self.chunk_size_increase = 2.0

    def stop(self):
        self.IS_RUN = False

    def get_suggested_scan_start_block(self):
        """获取我们应该开始扫描新事件的位置。

        如果没有先前的扫描，则从块 1 开始。
        否则，从最后一个结束块减去十个块开始。
        如果存在分叉，会重新扫描最后十个扫描的区块，以避免由于较小的单个区块工作（在以太坊中每小时发生一次）而造成的错误核算。
        这些启发式可以变得更加健壮，但这是为了简单的参考实现。
        """

        end_block = self.get_last_scanned_block()
        if end_block:
            return max(1, end_block)
        return 1

    async def get_suggested_scan_end_block(self, chain_reorg_safety_blocks):
        """获取关注的以太坊链上最后一个开采的区块。"""

        # 不要一直扫描到最后一个区块，因为这个区块可能还没有被开采
        try:
            return await self.web3.eth.block_number - chain_reorg_safety_blocks
        except Exception:
            return 0

    def get_last_scanned_block(self) -> int:
        return self.state.get_last_scanned_block()

    def delete_potentially_forked_block_data(self, after_block: int):
        """在区块链重组的情况下清除旧数据。"""
        self.state.delete_data(after_block)

    async def scan_chunk(self, start_block, end_block) -> Tuple[int, int, int]:
        """读取和处理块号之间的事件。

        如果 JSON-RPC 服务器出现问题，则动态减小块的大小。

        :return: tuple(实际结束区块编号,该区块何时被挖掘,已处理事件)
        """

        # 获取指定区块区间的所有事件(包括转账)
        block_timestamp, all_events = await self.fetch_events(start_block, end_block)

        # 开始根据事件生成数据表
        for event in all_events:
            self.state.process_event(event, self.contracts, self.new_dynamic_address)

        return end_block, block_timestamp, len(all_events)

    @async_retry
    async def fetch_block(self, block_number):
        try:
            result = await self.web3.eth.get_block(block_number, True)
            if result:
                BlockLog.save_logs([BlockLog.create_log(result)])
            return result
        except ClientResponseError as e:
            if e.status == 429:
                if self.switch_provider_handle:
                    self.switch_provider_handle()
                await asyncio.sleep(2)
            return block_number
        except Exception as e:
            self.logger.exception(f"fetch_block error : {e}")
            return block_number

    @async_retry
    async def fetch_receipt(self, tx_hash):
        try:
            result = await self.web3.eth.get_transaction_receipt(tx_hash)
            if result:
                ReceiptLog.save_logs([ReceiptLog.create_log(result)])
            return result
        except ClientResponseError as e:
            if e.status == 429:
                if self.switch_provider_handle:
                    self.switch_provider_handle()
                await asyncio.sleep(2)
            return tx_hash
        except Exception as e:
            self.logger.exception(f"fetch_receipt error : {e}")
            return tx_hash

    async def batch_fetch_block(self, block_numbers: list):
        tasks = []
        blocks = []
        for b in block_numbers:
            tasks.append(asyncio.create_task(self.fetch_block(b)))
        done, _ = await asyncio.wait(tasks)
        results = [t.result() for t in done]
        blocks = [b for b in results if isinstance(b, AttributeDict)]
        errs = [e for e in results if isinstance(e, AttributeDict) == False]
        blocks.sort(key=lambda o: o.number)
        return blocks, errs

    async def batch_fetch_receipt(self, transactions: list):
        tasks = []
        receipts = []
        for transaction in transactions:
            tasks.append(asyncio.create_task(self.fetch_receipt(transaction.hash)))
        done, _ = await asyncio.wait(tasks)
        results = [t.result() for t in done]
        receipts = [r for r in results if isinstance(r, AttributeDict)]
        errs = [e for e in results if isinstance(e, AttributeDict) == False]
        receipts.sort(key=lambda o: o.blockNumber)
        return receipts, errs

    def get_transactions_by_blocks(self, blocks):
        transactions = []
        for block in blocks:
            transactions += block.transactions
        return [transactions[i:i + self.max_scan_chunk_size] for i in range(0, len(transactions), self.max_scan_chunk_size)]

    def get_block_timestamp(self, blocks):
        return {b.number: b.timestamp for b in blocks}

    def get_transaction_map(self, transactions):
        return {t.hash.hex(): t for t in transactions}

    async def fetch_events(self, block_number, end_block) -> Tuple[int, List[EventInfo]]:
        blocks, errs = await self.batch_fetch_block([b for b in range(block_number, end_block + 1)])
        # 请求报错时这里会一直请求, 注意观察性能
        while len(errs) > 0:
            b2, errs = await self.batch_fetch_block(errs)
            blocks += b2
            await asyncio.sleep(self.request_retry_seconds)

        transactions_group = self.get_transactions_by_blocks(blocks)
        block_timestamp = self.get_block_timestamp(blocks)
        timestamp = block_timestamp.get(blocks[0].number)
        # 获取所有加载的合约，以执行扫描
        contracts = self.events.getContractNames()
        eventLogs: List[EventInfo] = []
        for transactions in transactions_group:
            transaction_map = self.get_transaction_map(transactions)
            receipts, errs = await self.batch_fetch_receipt(transactions)
            while len(errs) > 0:
                r2, errs = await self.batch_fetch_receipt(errs)
                receipts += r2
                await asyncio.sleep(self.request_retry_seconds)
            for receipt in receipts:
                timestamp = block_timestamp.get(receipt.blockNumber)
                tx = transaction_map.get(receipt.transactionHash.hex())
                for contract in contracts:
                    adds = self.state.get_address(contract)
                    if len(adds) == 0:
                        continue
                    # 处理原生转账生成事件
                    hasTransfer = self.events.getHandle(contract, TRANSFER_EVENT_NAME)
                    if hasTransfer and tx.to in adds:
                        ei = EventInfo()
                        ei.index = -1
                        ei.eventName = TRANSFER_EVENT_NAME
                        ei.blockNumber = tx.blockNumber
                        ei.contract = contract
                        ei.timestamp = timestamp
                        # ei.event = evt
                        ei.receipt = receipt
                        ei.transaction = tx
                        eventLogs.append(ei)
                    # 处理合约事件
                    for log in receipt.logs:
                        evt = self.events.getEventData(self.web3, contract, log)
                        # evt.logIndex 块中日志索引位置的整数，待处理时为空
                        # 我们无法避免小的链重组,但至少我们必须避免尚未开采的区块
                        if evt and evt.logIndex is not None and evt.address in adds:
                            ei = EventInfo()
                            ei.eventName = evt.event
                            ei.index = evt.logIndex
                            ei.blockNumber = evt.blockNumber
                            ei.contract = contract
                            ei.timestamp = timestamp
                            ei.event = evt
                            ei.receipt = receipt
                            ei.transaction = tx
                            eventLogs.append(ei)
            await asyncio.sleep(self.request_interval_sec)

        eventLogs.sort(key=lambda o: (o.blockNumber, o.index))
        return timestamp, eventLogs

    def new_dynamic_address(self, contract: str, address: str):
        self.state.add_address(contract, address)

    async def scan_database(self, total: int, scan_size: int = 1000, progress_callback=Optional[Callable]) -> int:
        processed = 0
        offset = 0
        last_block = 0
        contracts = self.events.getContractNames()
        while processed < total:
            blocks = BlockLog.getLogs(offset, scan_size)
            for block in blocks:
                eventLogs: List[EventInfo] = []
                last_block = block.number
                tx_map = {t.hash.hex(): t for t in block.transactions}
                # 获取此块交易的所有receipts
                receipts = ReceiptLog.get_receipts(tx_map.keys())
                for receipt in receipts:
                    if receipt.status == 0:
                        continue
                    tx = tx_map.get(receipt.transactionHash.hex())
                    for contract in contracts:
                        adds = self.state.get_address(contract)
                        if len(adds) == 0:
                            continue
                        hasTransfer = self.events.getHandle(contract, TRANSFER_EVENT_NAME)
                        if hasTransfer and tx.to in adds:
                            ei = EventInfo()
                            ei.index = -1
                            ei.eventName = TRANSFER_EVENT_NAME
                            ei.blockNumber = tx.blockNumber
                            ei.contract = contract
                            ei.timestamp = block.timestamp
                            # ei.event = evt
                            ei.receipt = receipt
                            ei.transaction = tx
                            eventLogs.append(ei)
                        # 处理合约事件
                        for log in receipt.logs:
                            evt = self.events.getEventData(self.web3, contract, log)
                            if evt and evt.logIndex is not None and evt.address in adds:
                                ei = EventInfo()
                                ei.eventName = evt.event
                                ei.index = evt.logIndex
                                ei.blockNumber = evt.blockNumber
                                ei.contract = contract
                                ei.timestamp = block.timestamp
                                ei.event = evt
                                ei.receipt = receipt
                                ei.transaction = tx
                                eventLogs.append(ei)
                eventLogs.sort(key=lambda o: (o.blockNumber, o.index))
                # 调用handle处理逻辑
                for ei in eventLogs:
                    self.state.process_event(ei, self.contracts)
                if progress_callback:
                    progress_callback(block.number, block.timestamp, 1, len(eventLogs))
                offset += 1
                processed += 1
        self.state.end_chunk(last_block)
        return processed



    async def scan(self, start_block, end_block, progress_callback=Optional[Callable]) -> Tuple[list, int]:
        """执行扫描。

        假设数据库中的所有数据在 start_block 之前都是有效的（没有分叉）。
        :param start_block: 扫描的第一个块
        :param end_block: 扫描的最后一个块
        :param progress_callback: 如果这是 UI 应用程序，请更新扫描进度
        :param start_chunk_size: 第一次尝试通过 JSON-RPC 获取多少块
        :return: [所有处理的事件，使用的块数]
        """

        assert start_block <= end_block, "start_block:{} end_block:{}".format(start_block, end_block)

        self.IS_RUN = True
        current_block = start_block
        chunk_size = self.max_scan_chunk_size
        total_chunks_scanned = 0
        # 我们在此扫描周期中获得的所有已处理条目
        processed_event_count = 0
        while current_block <= end_block and self.IS_RUN:
            chunk_size = min(chunk_size, end_block - current_block + 1)
            self.state.start_chunk(current_block)
            estimated_end_block = current_block + chunk_size - 1
            current_end, block_timestamp, new_event_count = await self.scan_chunk(current_block, estimated_end_block)
            # print("block_timestamp:", block_timestamp)

            # 当前的块扫描在哪里结束 - 是否脱离了链？
            processed_event_count += new_event_count
            # 打印进度
            if progress_callback:
                progress_callback(start_block, end_block, current_block, block_timestamp, chunk_size - (estimated_end_block-current_end), new_event_count)
            # 设置下一个块开始的位置
            current_block = current_end + 1
            total_chunks_scanned += 1
            self.state.end_chunk(min(current_end, end_block))
            # 睡眠500
            time.sleep(self.request_interval_sec)
        return processed_event_count, total_chunks_scanned
