import logging
import asyncio
import pytest
import time
from pydantic import Field

from bollydog.models.base import Event, BaseMessage
from bollydog.service.message import MessageManager, register

logger = logging.getLogger(__name__)


class LogInfoCommand(BaseMessage):
    info: str = Field(default='info message')


class GenInfoCommand(BaseMessage):
    ...


async def log_info(message: LogInfoCommand, *args):
    print(message.model_dump())
    return message.model_dump()


async def timeout_log_info(message: LogInfoCommand, *args):
    await asyncio.sleep(0.5)
    print(message.model_dump())
    return message.model_dump()


@register
async def async_gen(message: GenInfoCommand, *args):
    yield LogInfoCommand(info='yield 1')
    yield RaiseException()
    await asyncio.sleep(0.5)
    yield LogInfoCommand(info='yield 2')


class RaiseException(Event):
    ...


async def raise_exception(message: RaiseException):
    raise Exception("test raise_exception")


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
    # try:
    #     for task in tasks:
    #         res = await task
    # except:
    #     pass
    command = GenInfoCommand()
    command.expire_time = 1
    await MessageManager.execute(command, None)


async def try_exception(coro):
    result = None
    try:
        result = await coro
    except Exception as e:
        # raise e
        print(e)
    return result


@pytest.mark.asyncio
async def test_task_group():
    msg1 = LogInfoCommand(info='test1', a=1, b=2)
    msg2 = LogInfoCommand(info='test2', a=3, b=4)
    coro1 = try_exception(asyncio.wait_for(log_info(msg1), timeout=5))
    coro2 = try_exception(asyncio.wait_for(timeout_log_info(msg2), timeout=2))
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(coro1)
        task2 = tg.create_task(coro2)
        # task1.add_done_callback(MessageManager.task_done_callback)
        # task2.add_done_callback(MessageManager.task_done_callback)
    print(task1.result())
    print(task2.result())
