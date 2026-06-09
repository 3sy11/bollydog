from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import mode

from bollydog.globals import _hub_ctx_stack
from bollydog.models.base import BaseCommand as Message, BaseEvent
from bollydog.models.service import AppService
from bollydog.service.config import DOMAIN
from bollydog.service.runner import CommandRunnerMixin

if TYPE_CHECKING:
    from bollydog.service.exchange import Exchange
    from bollydog.service.queue import Queue


class HubService(CommandRunnerMixin, AppService):
    """Service mode: messages go through Queue pipeline.

    dispatch(msg) -> exchange.bind_subscriber_callbacks (Events only)
                  -> queue.put(msg)
    HubService.run consumer -> queue.take() -> create_task(_process_and_complete)
                            -> _run_with_context -> queue.complete
    execute(msg) = dispatch(msg) + await msg.state
    """
    domain = DOMAIN
    commands = ['commands']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_runner()
        self._domains = None
        self._exchange = self._queue = None

    @property
    def exchange(self) -> Exchange:
        if not self._exchange: self._exchange = AppService._apps['bollydog.Exchange']
        return self._exchange
    @property
    def queue(self) -> Queue:
        if not self._queue: self._queue = AppService._apps['bollydog.Queue']
        return self._queue

    async def on_first_start(self) -> None:
        self.exit_stack.enter_context(_hub_ctx_stack.push(self))

    async def on_start(self) -> None:
        if type(self).commands: type(self)._load_commands(type(self).commands)
        await super().on_start()

    async def _submit(self, message: Message):
        sub = await self.dispatch(message)
        return await sub.state

    async def emit(self, event: Message):
        await self.dispatch(event)

    async def gather(self, commands: list) -> list:
        subs = [await self.dispatch(cmd) for cmd in commands]
        return await asyncio.gather(*(sub.state for sub in subs), return_exceptions=True)

    async def dispatch(self, message: Message) -> Message:
        self.exchange.bind_subscriber_callbacks(message)
        await self.queue.put(message)
        return message

    async def execute(self, message: Message):
        await self.dispatch(message)
        return await message.state

    async def _process_and_complete(self, message):
        try: await self._run_with_context(message)
        except Exception as e:
            if not message.state.done(): message.state.set_exception(e)
        self.queue.complete(message.iid)

    @mode.Service.task
    async def run(self):
        while not self.should_stop:
            message = await self.queue.take()
            if not message: break
            self.logger.info(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias}')
            self.add_future(self._process_and_complete(message))
