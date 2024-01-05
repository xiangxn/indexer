import datetime
import sys
import time
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable, Iterable

from web3 import Web3
from web3.exceptions import BlockNotFound
from eth_abi.codec import ABICodec
from web3.types import EventData

from web3._utils.filters import construct_event_filter_params
from web3._utils.events import get_event_data
from center.events import Events
from center.database.logs import EventLog, create_log, getLogCount, getLogs

from center.logger import Logger


class EventScannerState(ABC):
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
        """扫描仪完成了一些块。
        现在保留您所在州的所有数据。
        """

    @abstractmethod
    def save_events(self, losg: List[EventLog]) -> EventLog:
        """预存储事件数据到本地数据库"""

    @abstractmethod
    def check_event(self, eventLog: EventLog, new_contract_address: Optional[Callable], contracts: dict = None) -> Tuple[int, List[EventLog]]:
        """检查事件,此方法会先调用一次处理handle
        如果事件处理handle中调用了 new_contract_address 则说明有新的合约被创建,这种情况下回清理当前块以后的所有事件日志
        
        :param eventLog: 事件日志数据
        :param new_contract_address: 有新的合约被创建, 需要handle内调用
        :param contracts: 配置的固定合约dict
        :return: 如果没有新合约创建返回0,如果有时则返回被创建时的块号
        """

    @abstractmethod
    def process_event(self, eventLog: EventLog, contracts: dict = None) -> None:
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


class EventScanner:
    """扫描区块链中的事件并尽量不要过度滥用 JSON-RPC API。

    可用于实时扫描，因为它检测到较小的链重组和重新扫描。
    与简单的 web3.contract.Contract 不同，此扫描器可以一次扫描来自多个合约的事件。
    例如，您可以在同一次扫描中从所有代币中获取所有转账。

    您*应该*禁用 Web3 提供程序上的默认 `http_retry_request_middleware`，
    因为它无法正确限制和减少 `eth_getLogs` 块编号范围。
    """

    def __init__(self,
                 web3: Web3,
                 state: EventScannerState,
                 events: Events,
                 max_chunk_scan_size: int = 10000,
                 max_request_retries: int = 30,
                 request_interval_sec: float = 0.5,
                 request_retry_seconds: float = 3.0,
                 contracts: dict = dict(),
                 logger: Logger = None,
                 switch_provider_handle=None):
        """
        :param contract: web3智能合约对象
        :param events: 扫描的 web3 Event 管理对象
        :param filters: 传递给 get_logs 的过滤器
        :param max_chunk_scan_size: JSON-RPC API 限制我们查询的块数。 （建议：主网 10,000，测试网 500,000）
        :param max_request_retries: 当失败时重新尝试调用 JSON-RPC 的次数
        :param request_interval_sec: 每次JSON-RPC的间隔
        :param request_retry_seconds: 失败请求之间的延迟,让 JSON-RPC 服务器恢复
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
        self.max_request_retries = max_request_retries
        self.request_retry_seconds = request_retry_seconds
        self.request_interval_sec = request_interval_sec

        # 如果找到结果，考虑增加块大小的速度（开始获得命中后减慢扫描速度）
        self.chunk_size_decrease = 0.5

        # 如果没有找到结果，考虑如何增加块大小
        self.chunk_size_increase = 2.0

    def get_block_timestamp(self, block_num) -> datetime.datetime:
        """获取以太坊区块时间戳"""
        try:
            block_info = self.web3.eth.get_block(block_num)
        except BlockNotFound:
            # 区块还没挖，次链重组？
            return None
        last_time = block_info["timestamp"]
        return last_time
        # return datetime.datetime.utcfromtimestamp(last_time)

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

    def get_suggested_scan_end_block(self, chain_reorg_safety_blocks):
        """获取关注的以太坊链上最后一个开采的区块。"""

        # 不要一直扫描到最后一个区块，因为这个区块可能还没有被开采
        try:
            return self.web3.eth.blockNumber - chain_reorg_safety_blocks
        except Exception:
            return 0

    def get_last_scanned_block(self) -> int:
        return self.state.get_last_scanned_block()

    def delete_potentially_forked_block_data(self, after_block: int):
        """在区块链重组的情况下清除旧数据。"""
        self.state.delete_data(after_block)

    def scan_chunk(self, start_block, end_block) -> Tuple[int, int, int]:
        """读取和处理块号之间的事件。

        如果 JSON-RPC 服务器出现问题，则动态减小块的大小。

        :return: tuple(实际结束区块编号,该区块何时被挖掘,已处理事件)
        """
        block_timestamps = {}
        get_block_timestamp = self.get_block_timestamp

        # 缓存块时间戳以减少一些RPC开销,真正的解决方案可能包括更智能的块模型
        def get_block_when(block_num):
            if block_num not in block_timestamps:
                block_timestamps[block_num] = get_block_timestamp(block_num)
            return block_timestamps[block_num]

        # 获取指定区块区间的所有事件
        end_block_timestamp, all_events = self.fetch_events(start_block, end_block, get_block_when)

        # 检查日志是否存在创建新合约的事件,有则读取新合约的地址
        last_valid_block = end_block
        checked: List[EventLog] = []
        for event in all_events:
            valid_block, _checked = self.state.check_event(event, self.new_dynamic_address, self.contracts)
            checked += _checked
            if valid_block != 0 and valid_block < last_valid_block:
                last_valid_block = valid_block
                valid_block = 0

        # 处理有效块之内的含有创建动作的事件
        checked = [eventLog for eventLog in checked if eventLog.blockNumber <= last_valid_block]
        for eventLog in checked:
            self.state.process_event(eventLog, self.contracts)
        # 优先保存含创建动作的事件日志
        self.state.save_events(checked)

        # 过滤掉有效块之后的事件
        if last_valid_block != end_block or len(checked) > 0:
            all_events = [event for event in all_events if event.blockNumber <= last_valid_block]
            end_block = last_valid_block
            # 补扫可能漏掉的事件
            _, new_events = self.fetch_events(end_block, end_block, get_block_when)
            for event in new_events:
                tmp = [evt for evt in all_events if evt.sign == event.sign]
                if len(tmp) == 0:
                    all_events.append(event)

        # 清理掉已经处理(生成数据)过的事件
        valid_events: List[EventLog] = []
        for event in all_events:
            tmp = [evt for evt in checked if evt.sign == event.sign]
            if len(tmp) == 0:
                valid_events.append(event)

        # 开始根据事件生成数据表
        for event in valid_events:
            self.state.process_event(event, self.contracts)
            end_block_timestamp = event.timestamp
        self.state.save_events(valid_events)

        return end_block, end_block_timestamp, len(valid_events) + len(checked)

    def fetch_events(self, start_block, end_block, get_block_when) -> Tuple[int, List[EventLog]]:
        # _fetch_events_for_all_contracts = self._fetch_events_for_all_contracts
        _fetch_events_for_all_contracts = self._fetch_events_for_all
        # 获取所有加载的合约，以执行扫描
        contracts = self.events.getContractNames()
        eventLogs: List[EventLog] = []
        last_block_time = 0
        for contract in contracts:
            adds = self.state.get_address(contract)
            if len(adds) == 0:
                continue
            # 负责底层 web3 调用的 Callable
            def _fetch_events(_start_block, _end_block):
                return _fetch_events_for_all_contracts(self.web3, contract, self.get_filters(contract, adds), from_block=_start_block, to_block=_end_block)

            # 对 `get_logs` 进行 `n` 次重试，如果需要，可以降低块范围分次请求
            start_fetch_block = start_block
            while True:
                last_fetch_block, events = self._retry_web3_call(_fetch_events,
                                                                 start_block=start_fetch_block,
                                                                 end_block=end_block,
                                                                 retries=self.max_request_retries,
                                                                 delay=self.request_retry_seconds)
                for evt in events:
                    idx = evt.logIndex  # 块中日志索引位置的整数，待处理时为空
                    # 我们无法避免小的链重组,但至少我们必须避免尚未开采的区块
                    assert idx is not None, "Somehow tried to scan a pending block"
                    block_number = evt.blockNumber
                    # 从内存缓存中获取此事件发生时的 UTC 时间（块挖掘时间戳）
                    last_block_time = get_block_when(block_number)
                    # 存储事件日志到数据库
                    eventLog = create_log(last_block_time, contract, evt)
                    eventLogs.append(eventLog)
                if last_fetch_block < end_block:
                    start_fetch_block = last_fetch_block + 1
                else:
                    break
        return last_block_time, eventLogs

    def new_dynamic_address(self, contract: str, address: str):
        self.state.add_address(contract, address)

    def get_filters(self, contract_name, adds):
        filters = {}
        adds = list(set(adds))
        filters['address'] = adds
        _, topics = self.events.getTopics(contract_name)
        filters['topics'] = [topics]
        return filters

    def estimate_next_chunk_size(self, current_chuck_size: int, event_found_count: int):
        """尝试找出最佳块大小

        扫描器可能需要扫描整个区块链的所有事件
        * 希望最小化对空块的 API 调用
        * 希望确保一个扫描块不会尝试一次处理太多条目，因为尝试控制提交缓冲区大小和潜在的异步繁忙循环
        * 不要通过一次询问太多事件的数据来使服务 JSON-RPC API 的节点过载

        目前，以太坊 JSON-API 没有 API 来判断区块链中何时发生第一个事件，启发式算法会尝试加速块获取（块大小），直到我们看到第一个事件。

        这些启发式方法会根据我们是否看到事件以指数方式增加扫描块的大小。
        当遇到任何传输时，我们将返回一次只扫描几个块。
        从区块 1 开始进行全链扫描，每 20 个区块执行一次 JSON-RPC 调用是没有意义的。
        """

        if event_found_count > 0:
            # 当我们遇到第一个事件时，重置块大小窗口
            current_chuck_size = self.min_scan_chunk_size
        else:
            current_chuck_size *= self.chunk_size_increase

        current_chuck_size = max(self.min_scan_chunk_size, current_chuck_size)
        current_chuck_size = min(self.max_scan_chunk_size, current_chuck_size)
        return int(current_chuck_size)

    def scan_database(self, total: int, scan_size: int = 1000, progress_callback=Optional[Callable]) -> int:
        processed = 0
        offset = 0
        total = getLogCount()
        last_block = 0
        while processed < total:
            data = getLogs(offset, scan_size)
            for item in data:
                last_block = item.blockNumber
                # 如果有新创建的合约, 则读取新的合约地址
                self.state.check_event(item, self.new_dynamic_address, self.contracts)
                # 根据事件生成数据表
                self.state.process_event(item, self.contracts)
            count = len(data)
            if progress_callback:
                progress_callback(data[-1].blockNumber, data[-1].timestamp, count)
            offset += count
            processed += count
        self.state.end_chunk(last_block)
        return processed

    def stop(self):
        self.IS_RUN = False

    def scan(self, start_block, end_block, start_chunk_size=20, progress_callback=Optional[Callable]) -> Tuple[list, int]:
        """执行扫描。

        假设数据库中的所有数据在 start_block 之前都是有效的（没有分叉）。
        :param start_block: 扫描的第一个块
        :param end_block: 扫描的最后一个块
        :param start_chunk_size: 第一次尝试通过 JSON-RPC 获取多少块
        :param progress_callback: 如果这是 UI 应用程序，请更新扫描进度
        :return: [所有处理的事件，使用的块数]
        """

        assert start_block <= end_block, "start_block:{} end_block:{}".format(start_block, end_block)

        self.IS_RUN = True
        current_block = start_block
        chunk_size = start_chunk_size
        last_scan_duration = 0
        total_chunks_scanned = 0
        # 我们在此扫描周期中获得的所有已处理条目
        processed_event_count = 0
        while current_block <= end_block and self.IS_RUN:
            chunk_size = min(chunk_size, end_block - current_block + 1)
            self.state.start_chunk(current_block, chunk_size)
            # 将一些诊断信息打印到日志以尝试调整 JSON-RPC API 的性能
            estimated_end_block = current_block + chunk_size - 1
            self.logger.debug(
                f"Scanning events for blocks: {current_block} - {estimated_end_block}, chunk size {chunk_size}, last chunk scan took {last_scan_duration}, last logs found {processed_event_count}"
            )
            start = time.time()
            actual_end_block, end_block_timestamp, new_event_count = self.scan_chunk(current_block, estimated_end_block)

            # 当前的块扫描在哪里结束 - 是否脱离了链？
            current_end = actual_end_block
            last_scan_duration = time.time() - start
            processed_event_count += new_event_count
            # 打印进度
            if progress_callback:
                progress_callback(start_block, end_block, current_block, end_block_timestamp, chunk_size - (estimated_end_block - current_end), new_event_count)
            # 尝试猜测下一次要通过 `get_logs` API 获取多少块
            chunk_size = self.estimate_next_chunk_size(chunk_size, new_event_count)
            # 设置下一个块开始的位置
            current_block = current_end + 1
            total_chunks_scanned += 1
            self.state.end_chunk(min(current_end, end_block))
            # 睡眠500
            time.sleep(self.request_interval_sec)
        return processed_event_count, total_chunks_scanned

    def _retry_web3_call(self, func, start_block, end_block, retries, delay) -> Tuple[int, List[EventData]]:
        """一个自定义重试循环来降低块范围。

        如果 JSON-RPC 服务器无法在单个请求中处理所有传入的 `get_logs`,会重试并限制每次重试的块范围。
        例如 Go Ethereum 并未指出可接受的响应大小。
        它只是在服务器端失败，并显示“上下文已取消”警告。

        :param func: 触发以太坊 JSON-RPC 的可调用对象，如 func(start_block, end_block)
        :param start_block: 查询区块范围的初始开始区块
        :param end_block: 区块范围的初始结束区块
        :param retries: 重试次数
        :param delay: 重试之间的间隔时间
        """
        i = 0
        while i < retries and self.IS_RUN:
            try:
                return end_block, func(start_block, end_block)
            except Exception as e:
                # 假设这是 HTTPConnectionPool(host='localhost', port=8545): Read timed out。 （读取超时=10）
                # 来自以太坊。 这转化为服务器端的错误“上下文被取消”：
                # https://github.com/ethereum/go-ethereum/issues/20426
                if i < retries - 1:
                    # 提供比默认中间件更详细的信息
                    self.logger.warning(
                        f"Retrying events for block range {start_block} - {end_block} ({end_block - start_block + 1}) failed with '{e}', {i} retrying in {delay} seconds"
                    )
                    # 减少 `getBlocks` 范围
                    end_block = start_block + ((end_block - start_block) // 2)
                    # 让 JSON-RPC 恢复例如重启
                    time.sleep(delay)
                    i += 1
                    continue
                else:
                    if self.switch_provider_handle:
                        self.logger.warning("Out of retries, switch next api")
                        self.switch_provider_handle()
                        time.sleep(delay)
                        i = 0
                        continue
                    else:
                        self.logger.exception("Out of retries")
                        raise
        return end_block, []

    def _fetch_events_for_all(self, web3, contract_name: str, argument_filters: dict, from_block: int, to_block: int) -> List[EventData]:
        if from_block is None:
            raise TypeError("Missing mandatory keyword argument to getLogs: fromBlock")
        args = argument_filters.copy()
        args['fromBlock'] = from_block
        if to_block is not None:
            args['toBlock'] = to_block
        self.logger.debug(f"Querying eth_getLogs with the following parameters: {args}")
        logs = web3.eth.get_logs(args)
        # print("logs:", logs)
        if len(logs):
            self.logger.error(f"logs={from_block}-{to_block}: {logs}")
        all_events: List[EventData] = []
        for log in logs:
            evt = self.events.getEventData(web3, contract_name, log)
            # 注意：这原本是yield，但是延迟超时异常导致节流逻辑不起作用
            if evt:
                all_events.append(evt)
        return all_events

    def _fetch_events_for_all_contracts(self, web3, event, argument_filters: dict, from_block: int, to_block: int) -> Iterable:
        """使用 get_logs API 获取事件。

        此方法与任何合约实例分离。

        这是一种无状态方法，与 createFilter 不同。
        它可以安全地针对不提供 `eth_newFilter` API 的节点调用，例如 Infura。
        """

        if from_block is None:
            raise TypeError("Missing mandatory keyword argument to getLogs: fromBlock")

        # 目前没有办法使用公共 Web3.py API 来解决这个问题。
        # 这将返回事件的原始底层 ABI JSON 对象
        abi = event._get_event_abi()

        # 根据用于编译使用 ABI 的合约的 Solidity 版本，它可能具有 Solidity ABI 编码 v1 或 v2。
        # 只是假设在此处为 Web3 对象设置的默认值。
        # 更多信息 https://eth-abi.readthedocs.io/en/latest/index.html
        codec: ABICodec = web3.codec

        # 在这里，需要深入了解一下 Web3 内部，因为默认情况下不会公开此功能。
        # 基于人类可读的 Python 描述构造 JSON-RPC 原始过滤器表示即将事件名称转换为其 keccak 签名
        # 更新信息:
        # https://github.com/ethereum/web3.py/blob/e176ce0793dafdd0573acc8d4b76425b6eb604ca/web3/_utils/filters.py#L71
        data_filter_set, event_filter_params = construct_event_filter_params(abi,
                                                                             codec,
                                                                             address=argument_filters.get("address"),
                                                                             argument_filters=argument_filters,
                                                                             fromBlock=from_block,
                                                                             toBlock=to_block)

        self.logger.debug(f"Querying eth_getLogs with the following parameters: {event_filter_params}")

        # 在以太坊节点上调用 JSON-RPC API。
        # get_logs() 返回原始的 AttributedDict 实体
        logs = web3.eth.get_logs(event_filter_params)

        # 如 ABI 所述，将原始二进制数据转换为 Python 代理对象
        all_events = []
        for log in logs:
            # 使用 ABI 数据将原始 JSON-RPC 日志结果转换为人类可读的事件
            # 更多信息 processLog 如何在此处工作
            # https://github.com/ethereum/web3.py/blob/fbaf1ad11b0c7fac09ba34baff2c256cffe0a148/web3/_utils/events.py#L200
            evt = get_event_data(codec, abi, log)
            # 注意：这原本是yield，但是延迟超时异常导致节流逻辑不起作用
            all_events.append(evt)
        return all_events
