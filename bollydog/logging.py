import sys
import logging
import os
from logging import config
import structlog
from bollydog.globals import message

def _trace_message_processor(_, __, ed):
    ed['trace'] = getattr(message, 'trace_id', '--')[:2]+getattr(message, 'span_id', '--')[:2]+getattr(message, 'parent_span_id', '--')[:2]+':'+getattr(message, 'iid', '--')[:2]
    return ed

def _pre_processor(_, __, ed):
    ed['levelname'] = ed['_record'].levelname.upper()[0]
    return ed

def _metrics_processor(_, __, ed):
    return ed

def _export_processor(_, __, ed):
    return ed

columns=[
    structlog.dev.Column(
        "levelname",
        structlog.dev.LogLevelColumnFormatter(
            width=0,
            level_styles={k[0].upper():v for k, v in structlog.dev.ConsoleRenderer.get_default_level_styles().items()},
            reset_style=''
        ),
    ),
    structlog.dev.Column(
        "timestamp",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=structlog.dev.YELLOW,
            reset_style=structlog.dev.RESET_ALL,
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "trace",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=structlog.dev.BRIGHT + structlog.dev.MAGENTA,
            reset_style=structlog.dev.RESET_ALL,
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "funcName",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=structlog.dev.GREEN,
            reset_style=structlog.dev.RESET_ALL,
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "lineno",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=structlog.dev.GREEN,
            reset_style=structlog.dev.RESET_ALL,
            value_repr=str,
            postfix=':',
        ),
    ),

    structlog.dev.Column(
        "event",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=structlog.dev.BRIGHT + structlog.dev.MAGENTA,
            reset_style=structlog.dev.RESET_ALL,
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=structlog.dev.GREEN,
            reset_style=structlog.dev.RESET_ALL,
            value_repr=str,
            prefix='|',
        ),
    ),
]

LOGGING_DICT_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "plain": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processors": [
                _trace_message_processor,
                structlog.processors.TimeStamper(fmt="%Y%m%d-%H:%M:%S"),
                structlog.stdlib.ExtraAdder(allow=structlog.stdlib._LOG_RECORD_KEYS),
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        },
        "console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processors": [
                _trace_message_processor,
                _pre_processor,
                structlog.processors.TimeStamper(fmt="%Y%m%d-%H:%M:%S"),
                structlog.stdlib.ExtraAdder(allow=['funcName', 'lineno']),
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True, columns=columns),
            ],
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "plain",
            "filename": os.environ.get("BOLLYDOG_LOG_FILE","info.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 3,
            "encoding": "utf-8",
        },
        "console": {
            "level": os.environ.get("BOLLYDOG_LOG_LEVEL", "INFO"),
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
}


class ProxyLogger(logging.Logger):
    _file: logging.FileHandler
    _console: logging.StreamHandler

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.handlers = [self._file, self._console]
        self.propagate = False

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        stacklevel = 1 + stacklevel
        if not self.handlers or self.handlers != [self._file, self._console]:
            self.handlers = [self._file, self._console]

        fn, lno, func, sinfo = self.findCaller(stack_info, stacklevel)
        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()

        record = self.makeRecord(self.name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)
        self.handle(record)


structlog.stdlib.recreate_defaults()
logging.setLoggerClass(ProxyLogger)
logging.config.dictConfig(LOGGING_DICT_CONFIG)
ProxyLogger._file, ProxyLogger._console = logging.root.handlers
