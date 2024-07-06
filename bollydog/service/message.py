import asyncio
import inspect
import logging
import uuid
from functools import partial
from typing import Type, MutableMapping, List, Callable, Any, Dict, Tuple, Set, AsyncIterator

from bollydog.exception import HandlerTimeOutError, HandlerMaxRetryError
from mode.utils.imports import smart_import

from bollydog.models.base import BaseMessage, MessageName, MessageId, get_model_name, ModulePathWithDot
from bollydog.models.base import BaseService
from bollydog.globals import bus

logger = logging.getLogger(__name__)
HandlerName = str


class _MessageManager(BaseService):
    messages: Dict[MessageName, Type[BaseMessage]] = {}
    handlers: Dict[MessageName, Callable] = {}
    futures: MutableMapping[MessageId, Tuple[BaseMessage, asyncio.Future]] = {}
    mapping: Dict[MessageName, Set[HandlerName]] = {}

    def add_message(self, message: Type[BaseMessage], alias: str = None):
        message_name = alias or get_model_name(message)
        if message_name in self.messages:
            logging.warning(f'{message_name} already exists in {self.messages}')
        self.messages[message_name] = message

    def add_handler(self, handler: Callable):
        self.handlers[get_model_name(handler)] = handler

    def register_handler(self, message: Type[BaseMessage], handler: Callable):
        assert handler  # < async
        message_name = get_model_name(message)
        self.add_message(message)
        self.add_handler(handler)
        if message_name not in self.mapping:
            self.mapping[message_name] = set()
        self.mapping[message_name].add(get_model_name(handler))  # ? handler 全路径

    @classmethod
    def create_message(cls, name, **data):
        _Message = BaseMessage
        if name in cls.messages:
            _Message = cls.messages[name]
        return _Message(**data)

    def walk_module(self, module: ModulePathWithDot):
        logger.info(f'Loading handlers from {module}')
        try:
            module = smart_import(module)
            for name, func in inspect.getmembers(module, inspect.isfunction):
                for parameter in func.__annotations__.values():
                    if parameter == Any:
                        break
                    if issubclass(parameter, BaseMessage):
                        self.add_handler(func)
                        self.register_handler(parameter, func)
                        break
        except (ModuleNotFoundError, AttributeError) as e:
            logger.warning(f'Error: {e}')
        except Exception as e:
            logger.exception(e)

    def task_done_callback(self, task):
        message, future = self.futures[task.get_name()]
        try:
            if not future.cancelled():
                result = task.result()
                result = result[0] if isinstance(result, tuple) else result
                if not future.done():
                    future.set_result(result)
            # result, __mode_service_stopped_identifier = task.result()  # # 适配mode.WaitResult
        except (HandlerTimeOutError, HandlerMaxRetryError, AssertionError, RuntimeError) as e:
            logger.error(e)
            future.set_exception(e)
        except Exception as e:
            logger.exception(e)
            future.set_exception(e)
        finally:
            self.futures.pop(message.iid, None)  # < 序列化然后释放,或独立任务释放
            logger.info(f'{message.trace_id}|\001|{message.name}:{message.iid} from {message.parent_span_id or "0"}')
            return message.model_dump()

    def create_tasks(self, message: 'BaseMessage', protocol=None, callback: Callable = None) -> List[asyncio.Task]:  # < callback
        handlers = message.handlers
        if message.name in self.mapping:
            handlers += list(self.mapping[message.name])
        if not handlers:
            logger.debug(f'No handler found for {message.name},nothing will be done')
        handlers = [partial(self.handlers[h], message) for h in handlers]
        if protocol:
            handlers = [partial(h, protocol) for h in handlers]
        tasks = []
        # < 根据条件添加过程处理函数：异常处理，重试，超时
        for handler in handlers[::-1]:
            coro = handler()
            if isinstance(coro, AsyncIterator):
                coro = self.async_generator_task(coro)
            task = asyncio.create_task(coro, name=message.iid)
            task.add_done_callback(self.task_done_callback)
            tasks.append(task)
            self.futures[message.iid] = (message, message.state)
            message = message.model_copy(update={'iid': uuid.uuid4().hex, 'future': asyncio.Future()})
        return tasks

    async def async_generator_task(self, async_generator: AsyncIterator, ):
        result = None
        async for maybe_message in async_generator:
            if isinstance(maybe_message, BaseMessage):
                if bus:
                    await bus.put_message(maybe_message)
                else:
                    tasks = self.create_tasks(maybe_message)
                    result = await self.wait_many(tasks, timeout=maybe_message.expire_time)
            else:
                result = maybe_message
        else:
            return result


MessageManager = _MessageManager()  # # 不会被start
