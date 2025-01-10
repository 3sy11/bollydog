import asyncio
import logging
import inspect
from typing import Any, Awaitable, Callable, Dict, Type, Set
from mode.utils.imports import smart_import
from bollydog.models.base import BaseMessage, ModulePathWithDot, MessageName, get_model_name
from bollydog.globals import _protocol_ctx_stack, _message_ctx_stack, bus, _app_ctx_stack

logger = logging.getLogger(__name__)


class AppHandler(object):
    # < BaseService
    messages: Dict[MessageName, Type[BaseMessage]] = {}
    handlers: Dict[Type[BaseMessage], Set['AppHandler']] = {}

    def __init__(self, fun, app) -> None:
        self.fun = fun
        self.app = app
        self.isasyncgenfunction = inspect.isasyncgenfunction(fun)  # # noqa

    async def __call__(self, message) -> Any:
        with (
            _protocol_ctx_stack.push(self.app.protocol),
            _message_ctx_stack.push(message),
            _app_ctx_stack.push(self.app),
        ):
            if not self.isasyncgenfunction:
                result = await self.fun(message)
                if isinstance(result, BaseMessage):
                    msg = await self.callback(result)
                    result = await msg.state
            else:
                async_gen = self.fun(message)
                result = None
                try:
                    while True:
                        msg = await async_gen.asend(result)
                        if not isinstance(msg, BaseMessage):
                            result = msg
                            break
                        msg = await self.callback(msg)
                        result = await msg.state
                except StopAsyncIteration:
                    pass
            return result

    def __repr__(self) -> str:
        return f'{self.app}: {self.fun}'

    def __str__(self):
        return self.__repr__()

    @property
    def callback(self):
        return bus.put_message if bus.state == 'running' and _message_ctx_stack.top.qos == 0 else bus.execute

    @classmethod
    def register(cls, cmd, fun, app):
        self = cls(fun, app)
        cls.handlers.setdefault(cmd, set()).add(self)
        cls.messages[get_model_name(cmd)] = cmd
        cmd.domain = app.domain
        fun.__name__ = cmd.name

    @classmethod
    def walk_annotation(cls, fun, app):
        for name, parameter in inspect.signature(fun).parameters.items():
            try:
                if inspect.isclass(parameter.annotation) and issubclass(parameter.annotation, BaseMessage):
                    cls.register(parameter.annotation, fun, app)
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
                cls.walk_annotation(func, app)
            for name, command in inspect.getmembers(module, inspect.isclass):
                if issubclass(command, BaseMessage) and hasattr(command, '__call__') and inspect.iscoroutinefunction(command.__call__):
                    cls.register(command, command.__call__, app)
        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f'Error: {e}, {module} may have error, try to import {module}.py')
        except Exception as e:
            logger.exception(e)
