import asyncio
import logging

from mode.utils.imports import smart_import

from globals import message
from .app import maybe_continue
from .model import TaskList, TaskCount, TaskDoneE, ContinueMessage

logger = logging.getLogger(__name__)


async def task_list(command: TaskList = message):
    result = asyncio.all_tasks()
    result = {task.get_name(): [task._state, str(task.get_coro())] for task in result}  # # noqa
    return result


async def task_count(command: TaskCount = message):
    result = asyncio.all_tasks()
    return len(result)


async def task_done(event: TaskDoneE = message):
    logger.info("Task done: %s", event.task_name)


async def continue_message(command: ContinueMessage = message):
    _message = smart_import(command.message)
    return await maybe_continue(_message, protocol=None)
