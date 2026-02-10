import logging
import inspect
from typing import Any, Dict, Type, Callable, Awaitable, List, TYPE_CHECKING
from bollydog.models.base import Command, BaseMessage, MessageName, get_model_name
from bollydog.globals import _protocol_ctx_stack, _message_ctx_stack, hub, _app_ctx_stack

if TYPE_CHECKING:
    from bollydog.models.service import AppService

logger = logging.getLogger(__name__)

class AppHandler:
    messages: Dict[MessageName, Type[BaseMessage]] = {}
    commands: Dict[Type[Command], "AppHandler"] = {}

    def __init__(self, fun: Callable, app: "AppService" = None):
        self.fun = fun
        self.app = app
        self.isasyncgenfunction = inspect.isasyncgenfunction(fun)

    async def __call__(self, message: BaseMessage) -> Any:
        with (_protocol_ctx_stack.push(self.app.protocol), _message_ctx_stack.push(message), _app_ctx_stack.push(self.app)):
            if self.isasyncgenfunction:
                return await self._handle_async_generator(message)
            return await self._handle_async_function(message)

    async def _handle_async_function(self, message):
        next_message = await self.fun(message)
        if isinstance(next_message, Command):
            next_message = await self.call(next_message)
            return await next_message.state
        return next_message

    async def _handle_async_generator(self, message):
        result, gen = None, self.fun(message)
        try:
            while True:
                next_message = await gen.asend(result)
                if not isinstance(next_message, Command):
                    return next_message
                await self.call(next_message)
                result = await next_message.state
        except StopAsyncIteration:
            pass
        return result

    @property
    def call(self) -> Callable[[BaseMessage], Awaitable[BaseMessage]]:
        return hub.put_message if hub.state == "running" and _message_ctx_stack.top.qos == 0 else hub.execute

    @classmethod
    def get_message_handlers(cls, message: Type[BaseMessage]) -> List["AppHandler"]:
        if issubclass(message, Command):
            handler = cls.commands.get(message)
            return [handler] if handler else []
        return []

    def __repr__(self):
        return f"{self.app}: {self.fun}"
