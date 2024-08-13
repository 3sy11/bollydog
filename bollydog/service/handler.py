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
    handlers: Dict[MessageName, 'AppHandler'] = {}

    def __init__(self, fun, app) -> None:
        self.fun = fun
        self.app = app
        self.isasyncgenfunction = inspect.isasyncgenfunction(fun)  # # noqa
        self.callback = None

    async def __call__(self, message) -> Any:
        async with (_protocol_ctx_stack.push(self.app.protocol), _message_ctx_stack.push(message)):
            if not inspect.isasyncgenfunction(self.fun):
                result = await self.fun(message)
                if isinstance(result, BaseMessage):
                    return await self.callback(result)
            async for msg in self.fun(message):
                if not isinstance(msg, BaseMessage):
                    return msg
                result = await self.callback(msg)
            return result

    def __repr__(self) -> str:
        return f'{self.app}: {self.fun}'

    def __str__(self):
        return self.__repr__()

    @classmethod
    def register(cls, fun, app):
        self = cls(fun, app)
        self.handlers[get_model_name(fun)] = self

    @classmethod
    def auto_discover(cls, fun, app):
        for name, parameter in inspect.signature(fun).parameters.items():
            try:
                if inspect.isclass(parameter.annotation) and issubclass(parameter.annotation, BaseMessage):
                    cls.register(fun, app)
                    break
            except Exception as e:
                logger.warning(f'{e}')
                continue


register = AppHandler.register
