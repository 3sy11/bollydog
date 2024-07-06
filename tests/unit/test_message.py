import logging

import pytest
from pydantic import Field

from bollydog.models.base import Event, BaseMessage
from bollydog.service.message import MessageManager

logger = logging.getLogger(__name__)


class LogInfoCommand(BaseMessage):
    info: str = Field(default='info message')


async def log_info(message: LogInfoCommand):
    logger.info(message.model_dump())


class RaiseException(Event):
    ...


async def raise_exception(message: RaiseException):
    raise Exception("test")


MessageManager.register_handler(LogInfoCommand, log_info)
MessageManager.register_handler(RaiseException, raise_exception)


@pytest.mark.asyncio
async def test_message():
    command = LogInfoCommand(info='test', a=1, b=2)
    tasks = MessageManager.create_tasks(command)
    for task in tasks:
        res = await task
    # event = RaiseException()
    # tasks = MessageManager.create_tasks(event)
    # for task in tasks:
    #     res = await task
