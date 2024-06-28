import asyncio
from typing import Iterable

import mode
from core.exception import (
    ServiceRejectException,
    MessageValidationError,
    ServiceMaxSizeOfQueueError,
)
from core.models.config import ServiceConfig
from core.models.service import AppService
from core.service.router import Router

from globals import _protocol_ctx_stack, _bus_ctx_stack, _message_ctx_stack
from models.base import BaseMessage as Message
from service.message import MessageManager
from .config import service_config, QUEUE_MAX_SIZE


async def maybe_continue(message, protocol):
    bus = _bus_ctx_stack.top
    if bus:
        await bus.push_message(message)
    else:
        for handler in MessageManager.mapping.get(message.name, []):
            return await MessageManager.handlers[handler](message, protocol=protocol)


class BusService(AppService):
    queue: asyncio.Queue
    apps: dict
    router: Router

    def __init__(self, apps: Iterable[AppService] = None, **kwargs):
        super().__init__(**kwargs)
        self.queue = asyncio.Queue()
        self.router = Router.create_from(config=ServiceConfig())
        self.apps = {self.domain: self}
        self.add_service(self.router)
        for app in apps or []:
            self.add_service(app)

    @classmethod
    def create_from(cls, **kwargs):
        return super().create_from(config=service_config, **kwargs)

    async def on_first_start(self) -> None:
        await super(BusService, self).on_first_start()

    async def on_start(self) -> None:
        await super(BusService, self).on_start()
        self.exit_stack.enter_context(_bus_ctx_stack.push(self))  # # mode.Service.stop

    async def on_shutdown(self) -> None:
        await super(BusService, self).on_shutdown()

    async def on_started(self) -> None:
        for service in self.apps.values():
            if service == self:
                continue
            await service.maybe_start()
        self.logger.info(self.apps)
        self.logger.info(MessageManager.mapping)
        self.logger.info(MessageManager.messages)
        self.logger.info(MessageManager.handlers)
        # self.logger.debug('Debug On !!')

    def add_service(self, service: AppService):
        assert service.domain
        assert service.domain not in self.apps
        self.apps[service.domain] = service

    async def _is_valid(self, message: Message):

        if not self.apps.get(message.domain):
            raise MessageValidationError(f'{message.domain} is not a valid domain')

    async def put_message(self, message: Message):
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
            with _message_ctx_stack.push(message):
                app: AppService = self.apps.get(message.domain)
                self.logger.info(
                    f'{message.trace_id}|\001\001|{message.name}:{message.iid} from {message.parent_span_id or "0"}')
                with _protocol_ctx_stack.push(app.protocol):
                    tasks = MessageManager.create_tasks(message)
                    if tasks:
                        await self.wait_many(tasks, timeout=message.expire_time)
                await self.router.publish(message)

    @mode.Service.timer(1)
    async def pop_events(self):
        for app in self.apps.values():
            while app.protocol and app.protocol.events:
                await self.queue.put(app.protocol.events.pop())

    # @mode.Service.timer(60)
    # async def matrix(self):
    #     self.logger.debug(f'queue size: {self.queue.qsize()}')
