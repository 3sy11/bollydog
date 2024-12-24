import sys
import logging as _logging
from contextlib import contextmanager
from mode.utils.logging import redirect_stdouts as _redirect_stdouts

def log_record_factory(*args, **kwargs):
    record = _logging.LogRecord(*args, **kwargs)
    return record

class ColorFormatter(_logging.Formatter):
    def format(self, record: _logging.LogRecord) -> str:
        if hasattr(record, "color_message"):
            return getattr(record, "color_message")
        else:
            return super().format(record)

class BaseHandler(_logging.StreamHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formatter = ColorFormatter('%(asctime)s[%(levelname)s][%(name)s] -- %(message)s')


class BaseLogger(_logging.Logger):
    def __init__(self, name, level=_logging.NOTSET, redirect=0):
        super().__init__(name, level)
        self.addHandler(BaseHandler())
        self.propagate = False
        self.redirect = redirect

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        stacklevel = self.redirect + stacklevel + 1
        fn, lno, func, sinfo = self.findCaller(stack_info, stacklevel)
        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()

        if not self.handlers:
            self.propagate = True

        record = self.makeRecord(self.name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)
        self.handle(record)

root = _logging.RootLogger(_logging.NOTSET)
root.handlers.clear()
root.addHandler(BaseHandler())
_logging.root = _logging.Logger.root = root
_logging.Logger.manager = _logging.Manager(_logging.Logger.root)

_logging.setLoggerClass(BaseLogger)
_logging.setLogRecordFactory(log_record_factory)


@contextmanager
def redirect_stdouts(logger:BaseLogger):
    """
    rewrite mode.utils.loggging.redirect_stdouts for support stacklevel
    """
    logger.redirect+=1
    try:
        with _redirect_stdouts(logger) as proxy:
            yield proxy
    finally:
        logger.redirect-=1