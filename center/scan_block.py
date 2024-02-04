import asyncio
from center.logger import Logger
from web3 import Web3, AsyncWeb3
from web3.middleware import geth_poa_middleware, async_geth_poa_middleware
import time
from center.discord_bot import DiscordBot
from center.scanner_state import ScannerState
from center.events import Events
from tqdm import tqdm
import datetime
from center.block_scanner import BlockScanner
from aiohttp import ClientResponseError


def print_log(msg):
    print(f"\033[1;31;47m\t[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] {msg}\033[0m")


class ScanBlock:

    def __init__(self, config, mode: int = 0, debug: bool = False, **kv) -> None:
        """初始化服务
        :param config: 全局配置项
        :param mode: 0 从网络初始化扫描, 1 从数据库初始化扫描, 2 直接增量扫描
        :param debug: 是否启用debug模式
        """
        self.IS_CONTINUOUS = False
        self.RUN_SYNC = True
        self.is_debug = debug
        self.logger = Logger("sync", debug=self.is_debug)
        self.config = config['sync_cfg']
        self.db_config = config['mongo']
        self.public_config = config
        self.init_mode = mode
        self.api_index = 0
        self._init_web3()
        self.monitor = DiscordBot(self.public_config['discord'], self.logger)
        self.events = Events(self.web3, self.logger)
        self.state = ScannerState(config, self.events, logger=self.logger)
        self._init_scanner()

    def _init_web3(self):
        self.provider = AsyncWeb3.AsyncHTTPProvider(
            self.config['chain_api'][self.api_index],
            request_kwargs={
                'headers': {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
                }
            })
        self.provider.middlewares.clear()
        self.web3 = AsyncWeb3(self.provider)
        self.web3.middleware_onion.inject(async_geth_poa_middleware, layer=0)

    def _init_scanner(self):
        self.scanner = BlockScanner(
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

    def Stop(self):
        if self.scanner:
            self.scanner.stop()
        self.RUN_SYNC = False
        print_log("Stopping the sync service...")

    def switch_provider(self):
        """自动切换api
        """
        api_count = len(self.config['chain_api'])
        if api_count < 2: return
        if self.api_index + 1 < api_count:
            self.api_index += 1
        else:
            self.api_index = 0
        self._init_web3()
        self.events.web3 = self.web3
        self.scanner.web3 = self.web3
        self.post_msg(f"⚠️ API has been switched: {self.config['chain_api'][self.api_index]}")

    def post_msg(self, msg):
        self.monitor.push_message(msg)

    async def scan(self):
        chain_reorg_safety_blocks = self.config['chain_reorg_safety_blocks']
        # 假定所有已扫的块都是安全块，这里不在清除数据
        # self.scanner.delete_potentially_forked_block_data(self.state.get_last_scanned_block() - chain_reorg_safety_blocks)
        start_block = self.state.get_last_scanned_block() + 1
        end_block = await self.scanner.get_suggested_scan_end_block(chain_reorg_safety_blocks)
        blocks_to_scan = end_block - start_block + 1
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
                progress_bar.set_description(msg)
                progress_bar.update(chunk_size)

            # 运行扫描
            processed_count, total_chunks_scanned = await self.scanner.scan(start_block, end_block, progress_callback=_update_progress)

        self.state.save()
        duration = time.time() - start
        print_log(f"Scanned total {processed_count} events, in {duration} seconds, total {min(blocks_to_scan, total_chunks_scanned)} chunk scans performed")

    async def init_sync_scan(self, clean=True):
        """从配置的块开始在链上扫描
        """
        self.IS_CONTINUOUS = True
        if clean:
            self.state.reset()
            self.state.cleanCache()  #清除状态缓存
            self.state.dropData()  #删除数据
            self.state.dropLogs()  #删除日志
        try:
            await self.scan()
        except ClientResponseError as e:
            if e.status == 429:
                self.switch_provider()
                await self.init_sync_scan(False)
            else:
                msg = f"scan error: {e}"
                self.logger.exception(msg)
                self.post_msg(msg)
        except Exception as e:
            msg = f"scan error: {e}"
            self.logger.exception(msg)
            self.post_msg(msg)

    def Run(self):
        self.loop = asyncio.get_event_loop()
        if self.init_mode == 0:
            print_log("init data...")
            self.loop.run_until_complete(asyncio.wait([self.loop.create_task(self.init_sync_scan())]))
        elif self.init_mode == 1:
            print_log("init data from database...")
        print_log("init data complete.")
        print_log("Start incremental sync...")
