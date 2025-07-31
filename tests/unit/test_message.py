import logging
import asyncio
import pytest
from pydantic import Field

from bollydog.models.base import Event, BaseMessage
from bollydog.service.handler import AppHandler
from bollydog.service.app import HubService

logger = logging.getLogger(__name__)


from bollydog.models.base import Event, BaseMessage, Command

class LogInfoCommand(Command):
    domain: str = Field(default='service')
    info: str = Field(default='info message')


class GenInfoCommand(Command):
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
    hub = HubService.create_from(domain='service',apps=[])
    AppHandler.register(GenInfoCommand,async_gen, hub)
    AppHandler.register(LogInfoCommand,log_info, hub)
    AppHandler.register(RaiseException, raise_exception, hub)
    AppHandler.register(LogInfoCommand, timeout_log_info, hub)
    command = LogInfoCommand(info='test')
    for coro in hub.get_coro(command):
        res = await coro()
    command = GenInfoCommand()
    # expire_time 是 ClassVar，不能在实例上设置
    # command.expire_time = 1
    await hub.execute(command)


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
    msg1 = LogInfoCommand(info='test1')
    msg2 = LogInfoCommand(info='test2')
    coro1 = try_exception(asyncio.wait_for(log_info(msg1), timeout=5))
    coro2 = try_exception(asyncio.wait_for(timeout_log_info(msg2), timeout=2))
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(coro1)
        task2 = tg.create_task(coro2)
        # task1.add_done_callback(MessageManager.task_done_callback)
        # task2.add_done_callback(MessageManager.task_done_callback)
    print(task1.result())
    print(task2.result())
