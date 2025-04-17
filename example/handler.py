import asyncio
from pydantic import Field
from bollydog.models.base import Command

DOMAIN = 'example'


class TaskList(Command):
    domain: str = Field(default=DOMAIN)


class TaskCount(Command):
    domain: str = Field(default=DOMAIN)


async def task_list(command: TaskList):
    result = asyncio.all_tasks()
    result = {task.get_name(): [task._state, str(task.get_coro())] for task in result}  # # noqa
    return result

async def task_count(command: TaskCount):
    result = asyncio.all_tasks()
    return len(result)
