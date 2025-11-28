import logging
import inspect
import httpx
from typing import Any, Dict, Type, Callable, Union, Awaitable, AsyncGenerator, List, TYPE_CHECKING
from mode.utils.imports import smart_import
from bollydog.models.base import (Command,Event,BaseMessage,ModulePathWithDot,MessageName,get_model_name,)
from bollydog.globals import (_protocol_ctx_stack,_message_ctx_stack,hub,_app_ctx_stack,)
from pydantic import Field
from bollydog.config import HOSTNAME

logger = logging.getLogger(__name__)
DOMAIN = 'service'

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
                return await self._handle_async_function(message)

    async def _handle_async_function(self, message: BaseMessage) -> Any:
        # ? if result is Event, should return msg.iid by default
        next_message = await self.fun(message)
        if isinstance(next_message, (Command, Event)):
            next_message = await self.call(next_message)
            result = await next_message.state
        else:
            result = next_message
        return result

    async def _handle_async_generator(self, message: BaseMessage) -> Any:
        result = None
        gen = self.fun(message)
        try:
            while True:
                next_message = await gen.asend(result)
                if not isinstance(next_message, (Command, Event)):
                    result = next_message
                    break
                await self.call(next_message)
                result = await next_message.state
        except StopAsyncIteration:
            pass
        return result

    def __repr__(self) -> str:
        return f"{self.app}: {self.fun}"

    def __str__(self):
        return self.__repr__()

    @property
    def call(self) -> Callable[[BaseMessage], Awaitable[BaseMessage]]:
        return (
            hub.put_message
            if hub.state == "running" and _message_ctx_stack.top.qos == 0
            else hub.execute
        )

    @classmethod
    def register(cls, message: Type[BaseMessage], fun: HandlerFunction, app: "AppService") -> None:
        if not isinstance(message, Type) or not issubclass(message, (Command, Event)):
            return

        message.domain = app.domain
        # fun.__name__ = message.name
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


class HttpCommand(Command):
    """HTTP 远程调用 Command 包装类"""
    domain: str = Field(default=DOMAIN)
    url: str = Field(description="完整的目标 URL")
    method: str = Field(default="POST", description="HTTP 方法")
    original: dict = Field(description="原始 Command 的 model_dump() 数据")

    name = 'http'

    @classmethod
    def check(cls, command: Command) -> Union[Command, 'HttpCommand']:
        if command.execution == 'local-only' and not command.destination or command.destination == HOSTNAME:
            return command
        from bollydog.entrypoint.http.app import HttpService

        try:
            route_path, methods = HttpService.build_command_route_info(command.__class__)
            method = methods[0] if methods else "POST"
            url = command.destination.rstrip('/') + route_path
            original_data = command.model_dump()
            original_data.update({
                'host': command.host,
                'version': command.version,
                'module': command.module,
                'domain': command.domain,
                'name': command.name
            })
            return cls(url=url, method=method, original=original_data)
        except Exception as e:
            logger.warning(f"构造 HttpCommand 失败: {e}")
            return command

    async def __call__(command):
        try:
            async with httpx.AsyncClient(timeout=command.expire_time) as client:
                if command.method.upper() == "GET":
                    response = await client.get(command.url, params=command.original)
                else:
                    response = await client.post(command.url, json=command.original) # > TypeError('Object of type bytes is not JSON serializable')

                response.raise_for_status()
                result = response.json()
            yield result

        except Exception as e:
            logger.warning(f"HttpCommand 远程调用失败: {e}，降级到本地执行")

            original_data = command.original.copy()

            for name, msg_class in AppHandler.messages.items():
                if msg_class.__name__.lower() == original_data.get('name'):
                    message_class = msg_class
                    break
            else:
                raise ValueError(f"无法找到对应的 Command 类: {original_data.get('name')}")
            original_data.pop('state')
            fallback_command = message_class(**original_data)
            fallback_command.execution = "local-only"

            result = yield fallback_command
            yield result
