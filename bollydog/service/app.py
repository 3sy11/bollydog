import asyncio
import uuid
from typing import Iterable, List, Dict, Awaitable, Tuple, MutableMapping, Any

import mode

from bollydog.exception import (
    ServiceRejectException,
    MessageValidationError,
    ServiceMaxSizeOfQueueError,
    HandlerTimeOutError,
    HandlerMaxRetryError,
    HandlerNoneError
)
from bollydog.globals import _bus_ctx_stack
from bollydog.models.base import BaseMessage as Message, MessageId
from bollydog.models.config import ServiceConfig
from bollydog.models.service import AppService
from bollydog.service.handler import AppHandler
from bollydog.service.router import Router
from .config import service_config, QUEUE_MAX_SIZE


class BusService(AppService):
    queue: asyncio.Queue
    apps: dict
    router: Router
    futures: MutableMapping[MessageId, Tuple[Message, asyncio.Future]] = {}
    tasks: Dict[MessageId, List[Any]] = {}
    app_handler = AppHandler

    def __init__(self, apps: Iterable[AppService] = None, **kwargs):
        super().__init__(**kwargs)
        self.queue = asyncio.Queue()
        self.router = Router.create_from(config=ServiceConfig())
        self.apps = {self.domain: self}
        self.add_service(self.router)
        for app in apps or []:
            self.add_service(app)
        self.exit_stack.enter_context(_bus_ctx_stack.push(self))  # # mode.Service.stop

    @classmethod
    def create_from(cls, **kwargs) -> 'BusService':
        return super().create_from(config=service_config, **kwargs)

    async def on_started(self) -> None:
        for service in self.apps.values():
            if service == self:
                continue
            await service.maybe_start()
        self.logger.info(self.apps)

    def add_service(self, service: AppService):
        assert service.domain
        assert service.domain not in self.apps
        self.apps[service.domain] = service

    async def _is_valid(self, message: Message):
        if not self.apps.get(message.domain):
            raise MessageValidationError(f'{message.domain} is not a valid domain')

    async def put_message(self, message: Message) -> Message:
        if self.should_stop:
            raise ServiceRejectException()
        if self.queue.qsize() > QUEUE_MAX_SIZE:
            raise ServiceMaxSizeOfQueueError('Queue is full')
        await self._is_valid(message)
        await self.queue.put(message)
        self.logger.debug(f'{message.iid} from {message.parent_span_id or "0"}')
        return message

    @mode.Service.task
    async def run(self):
        while not self.should_stop or not self.queue.empty():
            if self.queue.empty():
                await asyncio.sleep(0.1)
                continue
            message: Message = await self.queue.get()
            self.logger.debug(f'{message.module}-{message.domain}-{message.name}')
            app: AppService = self.apps.get(message.domain)
            self.logger.info(
                f'{message.trace_id}|\001\001|{message.name}: {message.iid} from {message.parent_span_id or "0"}')
            await self.execute(message)
            await self.router.publish(message)

    @mode.Service.task
    async def pop_events(self):
        while True:
            for app in self.apps.values():
                while app.protocol and app.protocol.events:
                    await self.queue.put(app.protocol.events.pop())
            await asyncio.sleep(1)

    def task_done_callback(self, task):
        message, future = self.futures.pop(task.get_name())
        try:
            if not future.cancelled():
                result = task.result()
                if not future.done():
                    future.set_result(result)
        except (HandlerTimeOutError, HandlerMaxRetryError, TimeoutError) as e:
            if message.delivery_count:
                message.delivery_count -= 1
                self._execute(message, task.get_coro())
            else:
                self.logger.error(e)
                future.set_exception(e)
        except (AssertionError, StopAsyncIteration, RuntimeError) as e:
            self.logger.error(e)
            future.set_exception(e)
        except Exception as e:
            self.logger.exception(e)
            future.set_exception(e)
        finally:
            self.logger.info(
                f'{message.trace_id}|\001|{message.name}: {message.iid} from {message.parent_span_id or "0"}')
            return message.model_dump()

    def get_coro(self, message: Message) -> List[Awaitable]:
        # < handler from message
        handlers = []
        handlers.extend(message.handlers)
        if message.__class__ in self.app_handler.handlers:
            handlers += list(self.app_handler.handlers[message.__class__])
        coroutines = []
        for handler in handlers[::-1]:
            coroutine = asyncio.wait_for(handler(message), timeout=message.expire_time)
            coroutines.append(coroutine)
            message = message.model_copy(update={'iid': uuid.uuid4().hex, 'future': asyncio.Future()})
        if not coroutines:
            raise HandlerNoneError(f'No handler found for {message.name}, nothing will be done')
        return coroutines

    def _execute(self, message, coro):
        task = asyncio.create_task(coro, name=message.iid)
        task.add_done_callback(self.task_done_callback)
        self.futures[message.iid] = (message, message.state)
        return task

    async def execute(self, message: Message) -> Message:
        coroutines = self.get_coro(message)
        try:
            tasks = [self._execute(message, coro) for coro in coroutines]
            await asyncio.wait(tasks)
        except Exception as e:
            self.logger.error(f'{e}')
            message.state.set_result(str(e))
        return message
