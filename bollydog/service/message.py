import asyncio
import inspect
import logging
import uuid
import sys
from functools import partial, wraps
from typing import Type, MutableMapping, List, Callable, Any, Dict, Tuple, Set, AsyncIterator, Coroutine, AsyncGenerator

from bollydog.exception import HandlerTimeOutError, HandlerMaxRetryError
from mode.utils.imports import smart_import

from bollydog.models.base import BaseMessage, MessageName, MessageId, get_model_name, ModulePathWithDot
from bollydog.models.base import BaseService
from bollydog.globals import _protocol_ctx_stack, _message_ctx_stack

logger = logging.getLogger(__name__)
HandlerName = str


class _MessageManager(BaseService):
    messages: Dict[MessageName, Type[BaseMessage]] = {}
    handlers: Dict[MessageName, Callable] = {}
    futures: MutableMapping[MessageId, Tuple[BaseMessage, asyncio.Future]] = {}
    mapping: Dict[MessageName, Set[HandlerName]] = {}
    tasks: Dict[MessageId, List[Any]] = {}  # # < tasks状态管理，需要释放避免溢出

    def add_message(self, message: Type[BaseMessage], alias: str = None):
        message_name = alias or get_model_name(message)
        if message_name in self.messages:
            logging.warning(f'{message_name} already exists in {self.messages}')
        self.messages[message_name] = message

    def add_handler(self, handler: Callable):
        self.handlers[get_model_name(handler)] = handler

    def _run_async_generator(self, func):

        @wraps(func)
        async def _(message, protocol):
            result = None
            async for msg in func(message, protocol):
                result = await self.execute(msg, protocol)
            return result

        return _

    def register_handler(self, message: Type[BaseMessage], handler: Callable):
        assert handler  # < async
        if inspect.isasyncgenfunction(handler):
            handler = self._run_async_generator(handler)
        message_name = get_model_name(message)
        self.add_message(message)
        self.add_handler(handler)
        handlers = self.mapping.get(message_name, set())
        handlers.add(get_model_name(handler))
        self.mapping[message_name] = handlers

    def register(self, func):
        # # also could use as decorator
        for name, parameter in inspect.signature(func).parameters.items():
            if issubclass(parameter.annotation, BaseMessage):
                self.add_handler(func)
                self.register_handler(parameter.annotation, func)
                break

    @classmethod
    def create_message(cls, name, **data):
        _Message = BaseMessage
        if name in cls.messages:
            _Message = cls.messages[name]
        return _Message(**data)

    def walk_module(self, module: ModulePathWithDot):
        logger.info(f'Loading handlers from {module}')
        try:
            if isinstance(module, str):
                module = smart_import(module)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                self.register(func)
        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f'Error: {e}, {module} may have error, try to import {module}.py')
        except Exception as e:
            logger.exception(e)

    def task_done_callback(self, task):
        message, future = self.futures.pop(task.get_name())
        try:
            if not future.cancelled():
                result = task.result()
                if not future.done():
                    future.set_result(result)
        except (HandlerTimeOutError, HandlerMaxRetryError, AssertionError, StopAsyncIteration, RuntimeError, TimeoutError) as e:
            logger.error(e)
            future.set_exception(e)
        except Exception as e:
            logger.exception(e)
            future.set_exception(e)
        finally:
            # self.futures.pop(message.iid, None)  # < 序列化然后释放,或独立任务释放
            logger.info(f'{message.trace_id}|\001|{message.name}:{message.iid} from {message.parent_span_id or "0"}')
            # logger.debug(sys.getrefcount(task))
            return message.model_dump()

    def create_tasks(self, message: 'BaseMessage', protocol=None, callback: Callable = None) -> List[Coroutine]:
        handlers = message.handlers
        if message.name in self.mapping:
            handlers += list(self.mapping[message.name])
        if not handlers:
            logger.debug(f'No handler found for {message.name},nothing will be done')
        handlers = [self.handlers[h] for h in handlers]
        coroutines = []
        for handler in handlers[::-1]:
            coroutine = asyncio.wait_for(handler(message, protocol), timeout=message.expire_time)
            self.futures[message.iid] = (message, message.state)
            coroutines.append(coroutine)
            message = message.model_copy(update={'iid': uuid.uuid4().hex, 'future': asyncio.Future()})
        return coroutines

    async def execute(self, message, protocol):
        with (_protocol_ctx_stack.push(protocol), _message_ctx_stack.push(message)):
            coroutines = self.create_tasks(message, protocol)
            # await asyncio.gather(*coroutines)
            try:
                async with asyncio.TaskGroup() as tg:
                    for coroutine in coroutines:
                        task = tg.create_task(coro=coroutine, name=message.iid)
                        task.add_done_callback(self.task_done_callback)
                        await asyncio.sleep(0)

            except Exception as e:
                self.logger.error(f'{e}')
            await asyncio.sleep(0)


MessageManager = _MessageManager()
register = MessageManager.register
