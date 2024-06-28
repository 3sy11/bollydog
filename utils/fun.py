import sys
import types
from inspect import Parameter, Signature
from typing import Callable, Sequence


def create_coroutine_function_from_parameters(func: Callable,
                                              parameters: Sequence[Parameter],
                                              documentation=None,
                                              func_name=None,
                                              func_filename=None) -> Callable:

    """
    https://github.com/kubeflow/pipelines/blob/sdk-2.0.1/sdk/python/kfp/deprecated/components/_dynamic.py
    """

    new_signature = Signature(parameters)

    async def pass_locals():
        result = await dict_func(**locals())  # noqa
        return result

    code = pass_locals.__code__  # noqa
    mod_co_argcount = len(parameters)  # noqa
    mod_co_nlocals = len(parameters) # noqa
    mod_co_varnames = tuple(param.name for param in parameters)  # noqa
    mod_co_name = func_name or code.co_name
    if func_filename:
        mod_co_filename = func_filename
        mod_co_firstlineno = 1  # noqa
    else:
        mod_co_filename = code.co_filename
        mod_co_firstlineno = code.co_firstlineno  # noqa
    if sys.version_info >= (3, 8):
        modified_code = code.replace(
            co_argcount=mod_co_argcount,
            co_nlocals=mod_co_nlocals,
            co_varnames=mod_co_varnames,
            co_filename=mod_co_filename,
            co_name=mod_co_name,
            co_firstlineno=mod_co_firstlineno,
        )
    else:
        modified_code = types.CodeType(
            mod_co_argcount, code.co_kwonlyargcount, mod_co_nlocals,
            code.co_stacksize, code.co_flags, code.co_code, code.co_consts,
            code.co_names, mod_co_varnames, mod_co_filename, mod_co_name,
            mod_co_firstlineno, code.co_lnotab)

    default_arg_values = tuple(
        p.default for p in parameters if p.default != Parameter.empty
    )
    modified_func = types.FunctionType(
        modified_code, {
            'dict_func': func,
            'locals': locals
        },
        name=func_name,
        argdefs=default_arg_values)
    modified_func.__doc__ = documentation
    modified_func.__signature__ = new_signature

    return modified_func
