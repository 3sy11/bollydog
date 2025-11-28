import asyncio
import logging
from typing import Union
from pydantic import Field
from bollydog.models.base import Command
from bollydog.config import HOSTNAME
from bollydog.entrypoint.http.app import HttpService

logger = logging.getLogger(__name__)
DOMAIN = 'service'


class TaskList(Command):
    domain: str = Field(default=DOMAIN)

class TaskCount(Command):
    domain: str = Field(default=DOMAIN)

class TaskState(Command):
    domain: str = Field(default=DOMAIN)

async def task_list(command: TaskList):
    result = asyncio.all_tasks()
    result = {task.get_name(): [task._state, str(task.get_coro())] for task in result}  # # noqa
    return result


async def task_count(command: TaskCount):
    result = asyncio.all_tasks()
    return len(result)

async def task_state(command: TaskState):
    count = yield TaskCount()
    tasks = yield TaskList()
    yield [count, tasks]

