import asyncio
import logging
import inspect
from typing import Any, Awaitable, Callable, Dict, Type, Set
from mode.utils.imports import smart_import
from bollydog.models.base import BaseMessage, ModulePathWithDot, MessageName, get_model_name
from bollydog.globals import _protocol_ctx_stack, _message_ctx_stack

logger = logging.getLogger(__name__)


class AppHandler(object):
    # < BaseService
    messages: Dict[MessageName, Type[BaseMessage]] = {}
    handlers: Dict[Type[BaseMessage], Set['AppHandler']] = {}

    def __init__(self, fun, app=None) -> None:
        self.fun = fun
        self.app = app
        self.isasyncgenfunction = inspect.isasyncgenfunction(fun)  # # noqa
        self.callback = None

    async def __call__(self, message) -> Any:
        with (_protocol_ctx_stack.push(self.app.protocol), _message_ctx_stack.push(message)):
            if not self.isasyncgenfunction:
                result = await self.fun(message)
                if isinstance(result, BaseMessage):
                    return await self.callback(result)
                return result
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
    def register(cls, fun, app=None):
        for name, parameter in inspect.signature(fun).parameters.items():
            try:
                if inspect.isclass(parameter.annotation) and issubclass(parameter.annotation, BaseMessage):
                    self = cls(fun, app)
                    cls.handlers.setdefault(parameter.annotation, set()).add(self)
                    cls.messages[get_model_name(parameter.annotation)] = parameter.annotation
                    break
            except Exception as e:
                logger.warning(f'{e}')
                continue

    @classmethod
    def walk_module(cls, module: ModulePathWithDot, app=None):
        logger.info(f'Loading handlers from {module}')
        try:
            if isinstance(module, str):
                module = smart_import(module)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                cls.register(func, app)
        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f'Error: {e}, {module} may have error, try to import {module}.py')
        except Exception as e:
            logger.exception(e)


register = AppHandler.register
