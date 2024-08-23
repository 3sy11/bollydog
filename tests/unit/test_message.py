import logging
import asyncio
import pytest
from pydantic import Field

from bollydog.models.base import Event, BaseMessage
from bollydog.service.handler import AppHandler
from bollydog.service.app import BusService

logger = logging.getLogger(__name__)


class LogInfoCommand(BaseMessage):
    domain: str = Field(default='service')
    info: str = Field(default='info message')


class GenInfoCommand(BaseMessage):
    domain: str = Field(default='service')
    ...


async def log_info(message: LogInfoCommand, *args):
    print(message.model_dump())
    return message.model_dump()


async def timeout_log_info(message: LogInfoCommand, *args):
    await asyncio.sleep(0.5)
    print(message.model_dump())
    return message.model_dump()


async def async_gen(message: GenInfoCommand, *args):
    yield LogInfoCommand(info='yield 1')
    yield RaiseException()
    await asyncio.sleep(0.5)
    yield LogInfoCommand(info='yield 2')


class RaiseException(Event):
    ...


async def raise_exception(message: RaiseException):
    raise TimeoutError("test raise_exception")


@pytest.mark.asyncio
async def test_message():
    bus = BusService.create_from(apps=[])
    AppHandler.register(async_gen, bus)
    AppHandler.register(log_info, bus)
    AppHandler.register(raise_exception, bus)
    AppHandler.register(timeout_log_info, bus)
    command = LogInfoCommand(info='test', a=1, b=2)
    for coro in bus.get_coro(command):
        res = await coro()
    command = GenInfoCommand()
    command.expire_time = 1
    await bus.execute(command)


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
