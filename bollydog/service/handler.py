import asyncio
import logging
import inspect
from typing import Any, Dict, Type, Callable, Union, Awaitable, AsyncGenerator
from mode.utils.imports import smart_import
from bollydog.models.base import Command, Event, BaseMessage, ModulePathWithDot, MessageName, get_model_name
from bollydog.models.service import AppService
from bollydog.globals import _protocol_ctx_stack, _message_ctx_stack, hub, _app_ctx_stack

logger = logging.getLogger(__name__)

HandlerFunction = Callable[[BaseMessage], Union[Awaitable[Union[Command, Event, Any]], AsyncGenerator[Union[Command, Event, Any], Any]]]


class AppHandler(object):
    messages: Dict[MessageName, Type[Command]] = {}
    handlers: Dict[Type[Command], 'AppHandler'] = {}

    def __init__(self, fun: HandlerFunction, app: AppService) -> None:
        self.fun: HandlerFunction = fun
        self.app: AppService = app
        self.isasyncgenfunction: bool = inspect.isasyncgenfunction(fun)

    async def __call__(self, message: BaseMessage) -> Any:
        with (
            _protocol_ctx_stack.push(self.app.protocol),
            _message_ctx_stack.push(message),
            _app_ctx_stack.push(self.app),
        ):
            if self.isasyncgenfunction:
                return await self._handle_async_generator(message)
            else:
                return await self._handle_sync_function(message)

    async def _handle_sync_function(self, message: BaseMessage) -> Any:
        # ? if result is Event, should return msg.iid by default
        result = await self.fun(message)
        if not isinstance(result, (Command, Event)):
            return result
        result = await self.callback(result)
        return result

    async def _handle_async_generator(self, message: BaseMessage) -> Any:
        result = None
        try:
            while True:
                result = await self.fun(message).asend(result)
                if not isinstance(result, (Command, Event)):
                    return result
                result = await self.callback(result)
        except StopAsyncIteration:
            return result

    def __repr__(self) -> str:
        return f'{self.app}: {self.fun}'

    def __str__(self):
        return self.__repr__()

    @property
    def callback(self) -> Callable[[BaseMessage], Awaitable[BaseMessage]]:
        return hub.put_message if hub.state == 'running' and _message_ctx_stack.top.qos == 0 else hub.execute

    @classmethod
    def register(cls, cmd: Type[Command], fun: HandlerFunction, app: AppService) -> None:
        if cmd in cls.handlers:
            logger.warning(f'Command {cmd.__name__} already has a handler, skipping registration')
            return
            
        self = cls(fun, app)
        cls.handlers[cmd] = self
        cls.messages[get_model_name(cmd)] = cmd
        cmd.domain = app.domain
        fun.__name__ = cmd.name

    @classmethod
    def walk_annotation(cls, fun: HandlerFunction, app: AppService) -> None:
        for name, parameter in inspect.signature(fun).parameters.items():
            try:
                if inspect.isclass(parameter.annotation) and issubclass(parameter.annotation, Command):
                    cls.register(parameter.annotation, fun, app)
                    break
            except Exception as e:
                logger.warning(f'{e}')
                continue

    @classmethod
    def walk_module(cls, module: ModulePathWithDot, app: AppService = None) -> None:
        logger.info(f'Loading handlers from {module}')
        try:
            if isinstance(module, str):
                module = smart_import(module)
            for name, command in inspect.getmembers(module, inspect.isclass):
                if issubclass(command, Command) and hasattr(command, '__call__') and command not in cls.handlers:
                    if inspect.iscoroutinefunction(command.__call__) or inspect.isasyncgenfunction(command.__call__):
                        cls.register(command, command.__call__, app)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                cls.walk_annotation(func, app)
        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f'Error: {e}, {module} may have error, try to import {module}.py')
        except Exception as e:
            logger.exception(e)
