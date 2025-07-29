import logging
import inspect
from typing import Any, Dict, Type, Callable, Union, Awaitable, AsyncGenerator, List, TYPE_CHECKING
from mode.utils.imports import smart_import
from bollydog.models.base import (Command,Event,BaseMessage,ModulePathWithDot,MessageName,get_model_name,)
from bollydog.globals import (_protocol_ctx_stack,_message_ctx_stack,hub,_app_ctx_stack,)

if TYPE_CHECKING:
    from bollydog.models.service import AppService

logger = logging.getLogger(__name__)
HandlerFunction = Callable[[BaseMessage],Union[Awaitable[Union[Command, Event, Any]],AsyncGenerator[Union[Command, Event, Any], Any],],]

class AppHandler(object):
    messages: Dict[MessageName, Type[BaseMessage]] = {}
    commands: Dict[Type[Command], "AppHandler"] = {}
    events: Dict[Type[Event], List["AppHandler"]] = {}

    def __init__(self, fun: HandlerFunction, app: "AppService") -> None:
        self.fun: HandlerFunction = fun
        self.app: "AppService" = app
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
            gen = self.fun(message)
            while True:
                if result is None:
                    result = await gen.__anext__()
                else:
                    result = await gen.asend(result)
                if not isinstance(result, (Command, Event)):
                    return result
                result = await self.callback(result)
        except StopAsyncIteration:
            return result

    def __repr__(self) -> str:
        return f"{self.app}: {self.fun}"

    def __str__(self):
        return self.__repr__()

    @property
    def callback(self) -> Callable[[BaseMessage], Awaitable[BaseMessage]]:
        return (
            hub.put_message
            if hub.state == "running" and _message_ctx_stack.top.qos == 0
            else hub.execute
        )

    @classmethod
    def register(
        cls, message: Type[BaseMessage], fun: HandlerFunction, app: "AppService"
    ) -> None:
        if not issubclass(message, (Command, Event)):
            logger.warning(f"Unknown message type {message}, skipping registration")
            return

        message.domain = app.domain
        fun.__name__ = message.name
        cls.messages[get_model_name(message)] = message

        if issubclass(message, Command):
            if message in cls.commands:
                logger.warning(f"Command {message.__name__} already has a handler, skipping registration")
                return
            cls.commands[message] = cls(fun, app)

        elif issubclass(message, Event):
            if message not in cls.events:
                cls.events[message] = []
            for handler in cls.events[message]:
                if handler.fun == fun and handler.app == app:
                    logger.warning(f"Event {message.__name__} handler already registered for {app}, skipping")
                    return
            cls.events[message].append(cls(fun, app))

    @classmethod
    def walk_annotation(cls, fun: HandlerFunction, app: "AppService") -> None:
        signature = inspect.signature(fun)
        for name, parameter in signature.parameters.items():
            try:
                annotation = parameter.annotation
                if annotation == inspect.Parameter.empty:
                    continue
                if hasattr(annotation, "__origin__") and annotation.__origin__ is Union:
                    for arg in annotation.__args__ :
                        cls.register(arg, fun, app)
                else:
                    cls.register(annotation, fun, app)

            except Exception as e:
                logger.warning(f"Error processing annotation for parameter {name}: {e}")
                continue

    @classmethod
    def walk_module(cls, module: ModulePathWithDot, app: "AppService" = None) -> None:
        logger.info(f"Loading handlers from {module}")
        try:
            if isinstance(module, str):
                module = smart_import(module)
            for _name, _cls in inspect.getmembers(module, inspect.isclass):
                # # only support class with async __call__ method and issubclass of Command or Event
                if (issubclass(_cls, (Command, Event)) and hasattr(_cls, "__call__")
                    and (inspect.iscoroutinefunction(_cls.__call__) or inspect.isasyncgenfunction(_cls.__call__))):
                    cls.register(_cls, _cls.__call__, app)
            for _name, _func in inspect.getmembers(module, inspect.isfunction):
                cls.walk_annotation(_func, app)

        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f"Error: {e}, {module} may have error, try to import {module}.py")
        except Exception as e:
            logger.exception(e)

    @classmethod
    def get_message_handlers(cls, message: Type[BaseMessage]) -> List["AppHandler"]:
        if issubclass(message, Command):
            handler = cls.commands.get(message)
            return [handler] if handler else []
        elif issubclass(message, Event):
            return cls.events.get(message, [])
        return []
