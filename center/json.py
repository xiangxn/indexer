from collections.abc import Callable
import json
from typing import Any, Dict, List, Union, cast
from hexbytes import HexBytes
from web3.datastructures import AttributeDict


class JsonEncoder(json.JSONEncoder):

    def default(self, obj: Any) -> Union[Dict[Any, Any], str]:
        if isinstance(obj, AttributeDict):
            return { k: v for k, v in obj.items() }
        elif isinstance(obj, HexBytes):
            return f"HEXB__{obj.hex()}"
        elif isinstance(obj, bytes):
            return f"BYTE__{obj.hex()}"
        return json.JSONEncoder.default(self, obj)


class JsonDecoder(json.JSONDecoder):

    def __init__(self) -> None:
        super().__init__(object_hook=self.object_hook)

    def object_hook(self, d: dict):
        for k, v in d.items():
            if isinstance(v, str):
                if v.startswith("BYTE__"):
                    d[k] = bytes.fromhex(v.lstrip("BYTE__"))
                elif v.startswith("HEXB__"):
                    d[k] = HexBytes(v.lstrip("HEXB__"))
            elif isinstance(v, list):
                vlist = []
                for item in v:
                    if isinstance(item, str):
                        if item.startswith("BYTE__"):
                            vlist.append(bytes.fromhex(item.lstrip("BYTE__")))
                        elif item.startswith("HEXB__"):
                            vlist.append(HexBytes(item.lstrip("HEXB__")))
                    else:
                        vlist.append(item)
                d[k] = vlist
        return d


def json_decode(json_str: str) -> Dict[Any, Any]:
    try:
        decoded = json.loads(json_str, cls=JsonDecoder)
        return decoded
    except json.decoder.JSONDecodeError as exc:
        err_msg = 'Could not decode {} because of {}.'.format(repr(json_str), exc)
        # Calling code may rely on catching JSONDecodeError to recognize bad json
        # so we have to re-raise the same type.
        raise json.decoder.JSONDecodeError(err_msg, exc.doc, exc.pos)
