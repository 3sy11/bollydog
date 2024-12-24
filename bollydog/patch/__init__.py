import os
import re

import yaml
from bollydog.patch.logging import *  # noqa
from bollydog.config import IS_DEBUG
from mode.utils.imports import smart_import


# ---logging---
def patch_logging():
    import logging
    from loguru import logger

    logging.basicConfig(level=logging.DEBUG if IS_DEBUG else logging.INFO)
    """
    CRITICAL = 50
    FATAL = 50
    ERROR = 40
    WARNING = 30
    WARN = 50
    INFO = 20
    DEBUG = 10
    NOTSET = 0
    """

    loguru_mapping = {
        50: 'critical',
        40: 'error',
        30: 'warning',
        20: 'info',
        10: 'debug',
        0: 'trace',
    }

    def _log(self,  # # noqa
             level,
             msg,
             args,
             exc_info=None,
             extra=None,
             stack_info=False,
             stacklevel=1  # # noqa
             ):

        fn, lno, func, sinfo = logging.root.findCaller(stack_info, stacklevel)
        record = logging.root.makeRecord(logging.root.name, level, fn, lno, msg, args,
                                         exc_info, func, extra, sinfo)
        level = loguru_mapping[level]
        if exc_info and level != 'info':
            stacklevel = 2  # # noqa
            logger.opt(depth=stacklevel + 1).exception(record.getMessage())
        else:
            getattr(logger.opt(depth=stacklevel + 1), level)(record.getMessage())

    setattr(logging.Logger, '_log', _log)


# patch_logging()

# ---yaml---
pattern = re.compile(r".*?(\${\w+}).*?")


def env_var_constructor(loader, node):
    value = loader.construct_scalar(node)
    for item in pattern.findall(value):
        var_name = item.strip('${} ')
        value = value.replace(item, os.getenv(var_name, item))
    return value


def module_constructor(loader, node):
    value = loader.construct_scalar(node)
    return smart_import(value)


yaml.SafeLoader.add_constructor('!env', env_var_constructor)
yaml.SafeLoader.add_implicit_resolver('!env', pattern, None)
yaml.SafeLoader.add_constructor('!module', module_constructor)
