import datetime
import importlib
import os
from typing import Tuple
from center.decorator import new_contract
from center.logger import Logger
from center.utils import Utils, ROOT_PATH
from web3.types import LogReceipt, EventData
from eth_utils import encode_hex, event_abi_to_log_topic
from web3._utils.events import get_event_data


class Events:

    def __init__(self, web3, logger: Logger) -> None:
        self.web3 = web3
        self.logger = logger
        self.handlers = dict()
        self._load_contracts()
        self._loadHandlers()
        self._init_topic()
        # print(self.contracts)

    def _load_contracts(self):
        self.contracts = {}
        count = 0
        for filename in os.listdir(ROOT_PATH + "/abi"):
            if not filename.endswith(".json"):
                continue
            name = os.path.splitext(filename)[0]
            self.contracts[name] = {"handlers": {}, "topic_list": [], "entry": None, "topic_dict": None}
            self.contracts[name]['entry'] = self.web3.eth.contract(abi=Utils.loadAbi(name))
            count += 1
        self.logger.warning(f"Load {count} contract abi file in total.")

    def _loadHandlers(self):
        events_count = 0
        for filename in os.listdir(ROOT_PATH + "/eventhandler"):
            if not filename.startswith("mapping"):
                continue
            name = os.path.splitext(filename)[0]
            mod = importlib.__import__("center.eventhandler." + name, fromlist=["*"])
            contract = name.lstrip("mapping")
            handlers = {}
            for f in dir(mod):
                if f.startswith("handle"):
                    event = f.lstrip("handle")
                    func = getattr(mod, f)
                    if not str(func).startswith("<function new_contract."):
                        func = new_contract()(func)  #添加函数装饰,处理 check_create_contract
                    handlers[event] = func
                    events_count += 1
            self.contracts[contract]['handlers'] = handlers
        self.logger.warning(f"Load {events_count} contract event handle in total.")

    def _init_topic(self):
        for contract_name, contract in self.contracts.items():
            topic_list = []
            topic_dict = {}
            for event_name in contract['handlers'].keys():
                event = self.getEvent(contract_name, event_name)
                abi = event._get_event_abi()
                topic = encode_hex(event_abi_to_log_topic(abi))  # type: ignore
                topic_list.append(topic)
                topic_dict[topic] = event_name
            contract['topic_list'] = topic_list
            contract['topic_dict'] = topic_dict

    def getTopics(self, contract_name) -> Tuple[dict, list]:
        # print("self.contracts[contract_name]:", self.contracts[contract_name])
        topic_list = self.contracts[contract_name]['topic_list']
        topic_dict = self.contracts[contract_name]['topic_dict']
        return topic_dict, topic_list

    def getContractNames(self) -> list:
        """获取所有加载的合约名"""
        return self.contracts.keys()

    def getContract(self, contract_name):
        return self.contracts[contract_name]['entry']

    def getEvent(self, contract_name, event_name):
        return self.getContract(contract_name).events[event_name]

    def getEventData(self, web3, contract_name, log_entry: LogReceipt) -> EventData:
        topic_dict, _ = self.getTopics(contract_name)
        # print("topic_dict:", topic_dict, contract_name)
        topic_key = log_entry['topics'][0].hex()
        if topic_key not in topic_dict:
            return None
        event_name = topic_dict[topic_key]
        event = self.getEvent(contract_name, event_name)
        abi = event._get_event_abi()
        return get_event_data(web3.codec, abi, log_entry)

    def callHandle(self, contract, event, block_when, contracts, call_back, is_check=False):
        handle = self.contracts[contract]['handlers'][event.event]
        if handle:
            if is_check == False:
                self.logger.debug("New event: {}.{} at {} {}: {}".format(contract, event.event, event.blockNumber,
                                                                         datetime.datetime.utcfromtimestamp(block_when).isoformat(), event.address))
            try:
                handle(block_when, event, contracts, check_create_contract=call_back)
            except Exception as e:
                self.logger.exception(f"callHandle error: {e}")
        else:
            self.logger.warning(f"Event handler not implemented: {event.event}")
