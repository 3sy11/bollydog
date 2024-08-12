import asyncio
import logging
from typing import Any, Awaitable, Callable
from bollydog.globals import message
from .model import TaskList, TaskCount, TaskDoneE

logger = logging.getLogger(__name__)


async def task_list(command: TaskList = message, protocol=None):
    result = asyncio.all_tasks()
    result = {task.get_name(): [task._state, str(task.get_coro())] for task in result}  # # noqa
    return result


async def task_count(command: TaskCount = message, protocol=None):
    result = asyncio.all_tasks()
    return len(result)


async def task_done(event: TaskDoneE = message, protocol=None):
    logger.info("Task done: %s", event.task_name)


class AppHandler(object):

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __init__(self, fun: Callable[..., Awaitable]) -> None:
        self.fun: Callable[..., Awaitable] = fun

    async def __call__(self, obj: Any) -> Any:
        return await self.fun(obj)

    def __repr__(self) -> str:
        return repr(self.fun)
