import sys
import logging
import os
from logging import config
import structlog
from bollydog.globals import message, app

log_path = os.environ.get("BOLLYDOG_LOG_PATH", ".")
if log_path != ".":
    os.makedirs(log_path, exist_ok=True)

COLORS = {
    'RESET': "\033[0m",
    'BOLD': "\033[1m",
    'BLUE': "\033[34m",
    'ORANGE': "\033[38;5;214m",
    'YELLOW': "\033[33m",
    'PURPLE': "\033[35m",
    'GRAY': "\033[37m"
}

level_styles = {
    'DEBUG': COLORS['GRAY'],
    'INFO': COLORS['RESET'],
    'WARNING': COLORS['YELLOW'],
    'ERROR': COLORS['ORANGE'],
    'CRITICAL': COLORS['PURPLE'] + COLORS['BOLD'],
}

def _trace_message_processor(_, __, ed):
    ed['domain'] = getattr(app,'name', '*')
    ed['trace'] = getattr(message, 'trace_id', '--')[:2]+getattr(message, 'parent_span_id', '--')[:2]+':'+getattr(message, 'span_id', '--')[:2]
    return ed

def _pre_processor(_, __, ed):
    ed['levelname'] = ed['_record'].levelname.upper()
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
            level_styles={k.upper():v for k, v in level_styles.items()},
            reset_style=COLORS['RESET'],
        ),
    ),
    structlog.dev.Column(
        "timestamp",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['YELLOW'],
            reset_style=COLORS['RESET'],
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "domain",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['BOLD'] + COLORS['PURPLE'],
            reset_style=COLORS['RESET'],
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "trace",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['PURPLE'],
            reset_style=COLORS['RESET'],
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "funcName",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['BLUE'],
            reset_style=COLORS['RESET'],
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "lineno",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['BLUE'],
            reset_style=COLORS['RESET'],
            value_repr=str,
            postfix=':',
        ),
    ),

    structlog.dev.Column(
        "event",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['RESET'],
            reset_style=COLORS['RESET'],
            value_repr=str,
        ),
    ),
    structlog.dev.Column(
        "",
        structlog.dev.KeyValueColumnFormatter(
            key_style=None,
            value_style=COLORS['RESET'],
            reset_style=COLORS['RESET'],
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
        "info": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "plain",
            "filename": os.path.join(os.environ.get("BOLLYDOG_LOG_PATH","."), "info.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 3,
            "encoding": "utf-8",
        },
        "error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "plain",
            "filename": os.path.join(os.environ.get("BOLLYDOG_LOG_PATH","."), "error.log"),
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
            "handlers": ["console", "info", "error"],
            "propagate": False,
        },
    },
}


class ProxyLogger(logging.Logger):
    _info: logging.FileHandler
    _console: logging.StreamHandler
    _error: logging.FileHandler

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.handlers = [self._info, self._console, self._error]
        self.propagate = False

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        stacklevel = 1 + stacklevel
        if not self.handlers or self.handlers != [self._info, self._console, self._error]:
            self.handlers = [self._info, self._console, self._error]

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
ProxyLogger._console, ProxyLogger._info, ProxyLogger._error = logging.root.handlers
