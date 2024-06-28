class ServiceRejectException(Exception):
    pass


class ServiceMaxSizeOfQueueError(Exception):
    pass


class MessageValidationError(Exception):
    pass


class MessageEmptyHandlerError(Exception):
    pass


class HandlerTimeOutError(Exception):
    pass


class HandlerMaxRetryError(Exception):
    pass
