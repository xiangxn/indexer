import os
import hashlib
import json

ROOT_PATH = os.path.split(os.path.realpath(__file__))[0]


def retry(func):

    def inner(*args, **kwargs):
        ret = func(*args, **kwargs)
        max_retry = 3
        number = 0
        if not ret:
            while number < max_retry:
                number += 1
                print("尝试第:{}次".format(number))
                ret = func(*args, **kwargs)
                if ret:
                    break
        return ret

    return inner


def async_retry(func):

    async def inner(*args, **kwargs):
        ret = await func(*args, **kwargs)
        max_retry = 3
        number = 0
        if not ret:
            while number < max_retry:
                number += 1
                print("尝试第:{}次".format(number))
                ret = await func(*args, **kwargs)
                if ret:
                    break
        return ret

    return inner


class Utils:

    @classmethod
    def sha256(cls, data):
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def char_to_value(cls, c):
        oc = ord(c)
        if oc >= ord('a') and oc <= ord('z'):
            return (oc - ord('a')) + 6
        if oc >= ord('1') and oc <= ord('5'):
            return (oc - ord('1')) + 1
        return 0

    @classmethod
    def string_to_uint64(cls, strs):
        n = 0
        l = len(strs)
        cs = strs if l <= 12 else strs[0:12]
        for c in cs:
            n <<= 5
            n |= cls.char_to_value(c)
        n <<= (4 + 5 * (12-l))
        if l > 12:
            n |= cls.char_to_value(strs[12]) & int(0x0F)
        return n

    @classmethod
    def loadAbi(cls, name):
        cf = open(ROOT_PATH + "/abi/" + name + ".json", "r")
        abi = json.load(cf)
        cf.close()
        return abi

    @classmethod
    def dict_to_json(cls, dict: dict = dict()):
        obj = {}
        for key in dict:
            t = dict[key]
            if isinstance(t, bytes):
                obj[key] = t.decode(encoding='utf-8')
            else:
                obj[key] = t
        return obj
