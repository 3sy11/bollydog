import asyncio
from functools import partial
from typing import Iterable, List, Dict, Awaitable, Tuple, MutableMapping, Any, Coroutine

import mode

from bollydog.exception import (
    ServiceRejectException,
    MessageValidationError,
    ServiceMaxSizeOfQueueError,
    HandlerTimeOutError,
    HandlerMaxRetryError,
    HandlerNoneError
)
from bollydog.globals import _hub_ctx_stack
from bollydog.models.base import BaseMessage as Message, MessageId, Command, Event
from bollydog.models.service import AppService
from bollydog.service.handler import AppHandler
from bollydog.service.router import Router
from bollydog.config import QUEUE_MAX_SIZE
from bollydog.service.handler import HttpCommand

_DOMAIN='bollydog'
_NAME='hub'
_HANDLERS = ['bollydog.service.model','bollydog.service.handler' ]

class HubService(AppService):
    queue: asyncio.Queue
    apps: dict
    router: Router
    futures: MutableMapping[MessageId, Tuple[Message, asyncio.Future]] = {}
    tasks: Dict[MessageId, Any] = {}

    def __init__(self, domain=_DOMAIN, name=_NAME, handlers=_HANDLERS, apps: Iterable[AppService] = None, **kwargs):
        super().__init__(domain=domain, name=name, **kwargs)
        self.queue = asyncio.Queue()
        self.router = Router(domain=domain)
        self.add_dependency(self.router)
        self.apps = {self.name: self}
        for app in apps or []:
            self.add_service(app)
        for handler in handlers:
            AppHandler.walk_module(handler, self)
        self.exit_stack.enter_context(_hub_ctx_stack.push(self))  # # mode.Service.stop

    async def on_started(self) -> None:
        for service in self.apps.values():
            if service == self:
                continue
            await service.maybe_start()
        self.logger.info(self.apps)

    def add_service(self, service: AppService):
        assert service.name
        assert service.name not in self.apps
        self.apps[service.name] = service

    async def put_message(self, message: Message) -> Message:
        if self.should_stop:
            raise ServiceRejectException()
        if self.queue.qsize() > QUEUE_MAX_SIZE:
            raise ServiceMaxSizeOfQueueError(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} Queue is full')
        message = HttpCommand.check(message)  # < move to router, lifecycle manage. using router.check->HttpCommand.check
        await self.queue.put(message)
        self.logger.info(
            f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.domain}.{message.name}')
        return message

    @mode.Service.task
    async def run(self):
        while not self.should_stop or not self.queue.empty():
            if self.queue.empty():
                await asyncio.sleep(0.1)
                continue
            message: Message = await self.queue.get()
            self.logger.debug(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.domain}.{message.name} {message.model_dump()}')
            app: AppService = self.apps.get(message.domain)
            self.logger.info(
                f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.domain}.{message.name}')
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
                self.logger.debug(
                    f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.domain}.{message.name}')
        except (HandlerTimeOutError, HandlerMaxRetryError, TimeoutError) as e:
            if message.delivery_count:
                self.logger.info(
                    f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.domain}.{message.name} retrying {message.delivery_count}')
                self.futures[message.iid] = (message, future)
            else:
                self.logger.error(e)
                self.logger.error('Timeout or MaxRetry')
                future.set_exception(e)
        except (AssertionError, StopAsyncIteration, RuntimeError) as e:
            self.logger.error(e)
            future.set_exception(e)
        except Exception as e:
            self.logger.exception(e)
            future.set_exception(e)

    def get_coro(self, message: Message) -> List[partial[Coroutine]]:
        if not isinstance(message, (Command, Event)):
            raise HandlerNoneError(f'Message type {type(message).__name__} is not supported, only Command and Event are allowed')
            
        handlers = AppHandler.get_message_handlers(message.__class__)
        if not handlers:
            raise HandlerNoneError(f'No handlers found for {type(message).__name__} {message.name}')
            
        return [partial(handler, message=message) for handler in handlers]

    async def _execute(self, message, coro):
        self.futures[message.iid] = (message, message.state)
        done = asyncio.Event()
        while not message.state.done() and not message.state.cancelled():
            done.clear()
            c = asyncio.wait_for(coro(), timeout=message.expire_time)
            t = asyncio.create_task(c, name=message.iid)
            t.add_done_callback(self.task_done_callback)
            t.add_done_callback(lambda _: done.set())
            await done.wait()
            if message.state.cancelled() or message.state.done():
                break
            message.delivery_count -= 1

    async def execute(self, message: Message) -> Message:
        coroutines = self.get_coro(message)
        try:
            async with asyncio.TaskGroup() as tg:
                for coro in coroutines:
                    tg.create_task(self._execute(message, coro))
            await asyncio.sleep(0)
        except Exception as e:
            self.logger.error(f'{e}')
            message.state.set_result(str(e))
        return message
