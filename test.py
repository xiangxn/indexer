
import json
import re
from web3 import Web3

print(bytes.fromhex('1234').decode('utf-8'))

print(bytes.fromhex('7b2270').decode('utf-8'))
s = bytes.fromhex('7b2270223a227372632d3230222c226f70223a226465706c6f79222c227469636b223a2242616e676b6f6b222c226d6178223a223130303030222c226c696d223a22313030222c22666565223a22323030303030303030303030303030227d').decode('utf-8')
o = json.loads(s)
try:
    dd = 23
    print(o, o["po"])
except KeyError:
    print('key error')

print(dd)

ddddd = re.match("^[a-z0-9A-Z]{1,10}$", "alossrwgwrgdf3")


def is_ethereum_address(address):
    try:
        # 尝试用Web3来将字符串解析为地址
        web3 = Web3()
        return web3.toChecksumAddress(address)
    except ValueError:
        # 如果解析失败，则不是有效的以太坊地址
        return False

