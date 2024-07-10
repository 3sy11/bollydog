import asyncio
import logging

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

