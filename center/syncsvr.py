import asyncio
import datetime
import time
from tqdm import tqdm
from center.discord_bot import DiscordBot
from center.event_scanner import EventScanner
from center.scanner_state import ScannerState
from center.events import Events
from center.logger import Logger
from center.database.logs import getLogCount

from web3 import Web3
from web3.middleware import geth_poa_middleware


def print_log(msg):
    print(f"\033[1;31;47m\t[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] {msg}\033[0m")


class SyncSvr:

    def __init__(self, config, get_init=int, debug=False, **kv):
        """初始化服务
        :param config: 全局配置项
        :param get_init: 0 直接增量扫描, 1 从网络初始化扫描, 2 从数据库初始化扫描, 3 清除全部数据与指定块后的事件日志，重建数据
        :param debug: 是否启用debug模式
        """
        self.IS_CONTINUOUS = False
        self.RUN_SYNC = True
        self.is_debug = debug
        self.logger = Logger("sync", debug=debug)
        self.config = config['sync_cfg']
        self.db_config = config['mongo']
        self.public_config = config
        self.get_init = get_init
        self.api_index = 0
        self.provider = Web3.HTTPProvider(
            self.config['chain_api'][self.api_index],
            request_kwargs={
                'headers': {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
                }
            })
        self.provider.middlewares.clear()
        self.web3 = Web3(self.provider)
        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.events = Events(self.web3, self.logger)
        self.state = ScannerState(config, self.events, logger=self.logger)
        self.monitor = DiscordBot(self.public_config['discord'], self.logger)
        self._init_scanner()
        if get_init == 3:
            self.args_start_block = kv.pop("block", 0)

    def _init_scanner(self):
        self.scanner = EventScanner(
            logger=self.logger,
            web3=self.web3,
            state=self.state,
            events=self.events,
            switch_provider_handle=self.switch_provider,
            contracts=self.public_config['contracts'],
            request_interval_sec=self.config['request_interval_sec'],
            request_retry_seconds=self.config['request_retry_seconds'],
            max_request_retries=self.config['max_request_retries'],
            # 从 JSON-RPC 请求时的最大块数，并且我们不太可能超过 JSON-RPC 服务器的响应大小限制
            max_chunk_scan_size=self.config['max_chunk_scan_size'])

    def switch_provider(self):
        """自动切换api
        """
        api_count = len(self.config['chain_api'])
        if api_count < 2: return
        if self.api_index + 1 < api_count:
            self.api_index += 1
        else:
            self.api_index = 0
        api = self.config['chain_api'][self.api_index]
        self.provider = Web3.HTTPProvider(api)
        self.provider.middlewares.clear()
        self.web3 = Web3(self.provider)
        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.events.web3 = self.web3
        self.scanner.web3 = self.web3
        self.post_msg(f"⚠️ API has been switched: {api}")

    def post_msg(self, msg):
        self.monitor.push_message(msg)

    def scan(self):
        chain_reorg_safety_blocks = self.config['chain_reorg_safety_blocks']
        # 假定所有已扫的块都是安全块，这里不在清除数据
        # self.scanner.delete_potentially_forked_block_data(self.state.get_last_scanned_block() - chain_reorg_safety_blocks)
        start_block = max(self.state.get_last_scanned_block() + 1, self.config['start_block'])
        end_block = self.scanner.get_suggested_scan_end_block(chain_reorg_safety_blocks)
        blocks_to_scan = end_block - start_block + 1
        # print("blocks_to_scan:", blocks_to_scan,start_block,end_block)
        if blocks_to_scan < 1:
            self.logger.warning(f"Waiting for JSON-RPC API new block to sync {start_block}")
            return
        print_log(f"Scanning events from blocks {start_block} - {end_block}")

        total_chunks_scanned = 0
        # 在控制台中渲染进度条
        start = time.time()
        with tqdm(total=blocks_to_scan, unit='Block') as progress_bar:

            def _update_progress(start, end, current, current_block_timestamp, chunk_size, events_count):
                if current_block_timestamp:
                    formatted_time = datetime.datetime.utcfromtimestamp(current_block_timestamp).strftime("%d-%m-%Y")
                else:
                    formatted_time = "no block time available"
                msg = f"Current block: {current} ({formatted_time}), blocks in a scan batch: {chunk_size}, events processed in a batch {events_count}"
                # self.post_msg(msg)
                progress_bar.set_description(msg)
                progress_bar.update(chunk_size)

            # 运行扫描
            processed_count, total_chunks_scanned = self.scanner.scan(start_block, end_block, progress_callback=_update_progress)

        self.state.save()
        duration = time.time() - start
        print_log(f"Scanned total {processed_count} events, in {duration} seconds, total {min(blocks_to_scan, total_chunks_scanned)} chunk scans performed")

    def database_scan(self):
        total = getLogCount()
        total_events_scanned = 0
        start = time.time()
        with tqdm(total=total, unit='Event') as progress_bar:

            def _update_progress(current, current_block_timestamp, events_count):
                if current_block_timestamp:
                    formatted_time = datetime.datetime.utcfromtimestamp(current_block_timestamp).strftime("%d-%m-%Y")
                else:
                    formatted_time = "no block time available"
                progress_bar.set_description(f"Current block: {current} ({formatted_time}), events processed in a batch {events_count}")
                progress_bar.update(events_count)

            # 运行扫描
            total_events_scanned = self.scanner.scan_database(total, self.config['scan_database_step_size'], progress_callback=_update_progress)

        self.state.save()
        duration = time.time() - start
        print_log(f"Scanned total {total_events_scanned}/{total} events, in {duration} seconds.")

    async def init_sync_scan(self):
        self.IS_CONTINUOUS = True
        self.state.reset()
        self.state.cleanCache()  #清除状态缓存
        self.state.dropData()  #删除数据
        self.state.dropLogs()  #删除日志
        try:
            await self.loop.run_in_executor(None, self.scan)
            await asyncio.sleep(1)
        except Exception as e:
            msg = f"scan error: {e}"
            self.logger.exception(msg)
            self.post_msg(msg)

    async def init_database_scan(self):
        self.IS_CONTINUOUS = True
        self.state.reset()
        self.state.cleanCache()  #清除状态缓存
        self.state.dropData()  #删除数据
        try:
            await self.loop.run_in_executor(None, self.database_scan)
            await asyncio.sleep(1)
        except Exception as e:
            self.logger.exception(f"database scan error: {e}")

    async def init_database_scan_by_block(self):
        if self.args_start_block:
            self.IS_CONTINUOUS = True
            self.state.reset()
            self.state.cleanCache()  #清除状态缓存
            self.state.dropData()  #删除数据
            self.state.deleteLogs(self.args_start_block)  #删除大于指定块的事件日志
            self.args_start_block = 0
            try:
                await self.loop.run_in_executor(None, self.database_scan)
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.exception(f"database by block scan error: {e}")

    async def increment_sync_scan(self):
        try:
            if False == self.IS_CONTINUOUS:
                self.state.restore()
            while (self.RUN_SYNC):
                await self.loop.run_in_executor(None, self.scan)
                await asyncio.sleep(self.config['realtime_scan_interval_sec'])
        except Exception as e:
            msg = f"increment scan error: {e}"
            self.logger.exception(msg)
            self.post_msg(msg)

    def getInitTasks(self, loop):
        return [loop.create_task(self.init_sync_scan())]

    def getDatabaseTasks(self, loop):
        return [loop.create_task(self.init_database_scan())]

    def getIncrementTasks(self, loop):
        return [loop.create_task(self.increment_sync_scan())]

    def Run(self):
        loop = asyncio.get_event_loop()
        self.loop = loop
        if self.get_init == 1:
            print_log("init data...")
            loop.run_until_complete(asyncio.wait(self.getInitTasks(loop)))
        elif self.get_init == 2:
            print_log("init data from database...")
            loop.run_until_complete(asyncio.wait(self.getDatabaseTasks(loop)))
        elif self.get_init == 3:
            print_log("init data with block from database...")
            loop.run_until_complete(asyncio.wait([loop.create_task(self.init_database_scan_by_block())]))

        print_log("init data complete.")
        print_log("Start incremental sync...")
        loop.run_until_complete(asyncio.wait(self.getIncrementTasks(loop)))
        loop.close()

    def Stop(self):
        if self.scanner:
            self.scanner.stop()
        self.RUN_SYNC = False
        print_log("Stopping the sync service...")
