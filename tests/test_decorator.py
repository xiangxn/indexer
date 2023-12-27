import sys

sys.path.append('./')

import pytest
from typing import cast
from web3.types import (EventData)
from web3.datastructures import AttributeDict
from center.decorator import new_contract


class TestDecorator(object):

    def test_decorator(self):

        # check_create_contract
        def create(param1, param2):
            print(f"create fun params: {param1},{param2}")
            return False

        timestamp = 1000000
        event = cast(EventData, AttributeDict.recursive({"args": {"community": "0xd63fF0c26f14Aa9f1Dc05549736Dc19d2Ec077C8"}}))

        @new_contract("contract_name", "community")
        def test(timestamp: int, event: EventData, contracts: dict):
            return f"DO test."

        print(test)
        print("test are there decorators: ", str(test).startswith("<function new_contract."))
        print(test(timestamp, event, {}, check_create_contract=create))

        def test2(timestamp: int, event: EventData, contracts: dict):
            return f"DO test2."

        print("test2 are there decorators: ", str(test2).startswith("<function new_contract."))

        if not str(test2).startswith("<function new_contract."):
            test2 = new_contract()(test2)

        print("test2 are there decorators: ", str(test2).startswith("<function new_contract."))

        print(test2(timestamp, event, {}, check_create_contract=create))
