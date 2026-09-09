from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import mode

from bollydog.config import DOMAIN
from bollydog.globals import _hub_ctx_stack, message as current_message, services
from bollydog.models.base import BaseCommand as Message
from bollydog.models.service import AppService
from bollydog.service.runner import CommandRunnerMixin

if TYPE_CHECKING:
    from bollydog.service.exchange import Exchange
    from bollydog.service.queue import Queue


class HubService(CommandRunnerMixin, AppService):
    """Service mode: messages go through Queue pipeline.

    dispatch(msg) -> queue.put(msg)
    HubService.run consumer -> queue.take() -> create_task(_process_and_complete)
                            -> _run_with_context -> queue.complete
    execute(msg) = dispatch(msg) + await msg.state
    emit(topic)  = exchange.instantiate(topic) + dispatch each, without awaiting
    """
    domain = DOMAIN
    commands = ['commands']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._exchange = self._queue = None

    @property
    def exchange(self) -> Exchange:
        if not self._exchange: self._exchange = services['bollydog.Exchange']
        return self._exchange
    @property
    def queue(self) -> Queue:
        if not self._queue: self._queue = services['bollydog.Queue']
        return self._queue

    async def on_first_start(self) -> None:
        self.exit_stack.enter_context(_hub_ctx_stack.push(self))

    async def on_start(self) -> None:
        await super().on_start()

    async def _submit(self, message: Message):
        sub = await self.dispatch(message)
        return await sub.state

    async def emit(self, topic: str = None, event: Message = None, source: Message = None) -> list:
        """Publish an event. Fire-and-forget: the handlers are never awaited.

        event given   -- dispatch that instance, topic is ignored.
        event omitted -- topic (defaulting to the current message's destination)
                         is matched against Exchange and every Event class bound
                         to it is instantiated and dispatched.
        source given  -- its dump is appended to each event's data['events'] list.
        """
        events = [event] if event is not None else self.exchange.instantiate(topic or current_message.destination)
        for evt in events:
            if source is not None:
                evt.data.setdefault('events', []).append(source.model_dump())
            await self.dispatch(evt)
        return events

    async def gather(self, commands: list) -> list:
        subs = [await self.dispatch(cmd) for cmd in commands]
        return await asyncio.gather(*(sub.state for sub in subs), return_exceptions=True)

    async def dispatch(self, message: Message) -> Message:
        await self.queue.put(message)
        return message

    async def execute(self, message: Message):
        await self.dispatch(message)
        return await message.state

    async def _process_and_complete(self, message):
        try:
            await self._run_with_context(message)
        except asyncio.CancelledError:
            try:
                await message.on_cancel()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.exception(e)
            if not message.state.done():
                message.state.cancel()
        except Exception as e:
            if not message.state.done():
                message.state.set_exception(e)
        finally:
            self.queue.complete(message.iid)

    @mode.Service.task
    async def run(self):
        while not self.should_stop:
            message = await self.queue.take()
            if not message: break
            self.logger.info(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias}')
            fut = self.add_future(self._process_and_complete(message))
            self.queue.activate(message.iid, fut)

    def cancel(self, iid: str, msg: str = None) -> int:
        """Cancel a queued or in-flight command by iid.

        PENDING:    removed from Queue, state cancelled.
        IN_FLIGHT:  Task.cancel() -> CancelledError -> on_cancel() -> state cancelled.
        """
        return 1 if self.queue.cancel(iid, msg=msg) else 0
