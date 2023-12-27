def new_contract(contract_name: str = None, param_name: str = None):
    """
    事件处理器的装饰器, 用于处理在事件中创建新的合约
    :param contract_name: 被新创建的合约名, 同abi文件名
    :param param_name: 被新创建的合约地址在事件参数args中的字段名
    """
    def decorator(f):

        def wrapper(*args, **kw):
            pf = kw.pop("check_create_contract")
            if contract_name and param_name:
                is_check = pf(contract_name, args[1].args[param_name])
            else:
                is_check = pf(None, None)
            if is_check:
                return None
            return f(*args, **kw)

        return wrapper

    return decorator