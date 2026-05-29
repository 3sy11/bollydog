from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import mode

from bollydog.exception import HandlerTimeOutError, HandlerMaxRetryError
from bollydog.globals import _hub_ctx_stack, _protocol_ctx_stack, _message_ctx_stack, _app_ctx_stack, _session_ctx_stack
from bollydog.models.base import BaseCommand as Message, BaseEvent
from bollydog.models.service import AppService
from bollydog.service.config import DOMAIN

if TYPE_CHECKING:
    from bollydog.service.exchange import Exchange
    from bollydog.service.session import Session
    from bollydog.service.queue import Queue


class Hub(AppService):
    """Unified message pipeline: all messages go through Queue.

    dispatch(msg) -> exchange.bind_subscriber_callbacks (Events only)
                  -> queue.put(msg)
    Hub.run consumer -> queue.take() -> create_task(_process_and_complete)
                     -> _run_with_context -> queue.complete
    execute(msg) = dispatch(msg) + await msg.state
    """
    domain = DOMAIN
    commands = ['commands']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._before, self._after = [], []
        self._domains = None
        self._exchange = self._session = self._queue = None

    @property
    def exchange(self) -> Exchange:
        if not self._exchange: self._exchange = AppService._apps['bollydog.Exchange']
        return self._exchange
    @property
    def session(self) -> Session:
        if not self._session: self._session = AppService._apps['bollydog.Session']
        return self._session
    @property
    def queue(self) -> Queue:
        if not self._queue: self._queue = AppService._apps['bollydog.Queue']
        return self._queue

    async def on_first_start(self) -> None:
        self.exit_stack.enter_context(_hub_ctx_stack.push(self))
        self.exit_stack.enter_context(_session_ctx_stack.push(self.session))

    async def on_stop(self) -> None:
        pass

    async def on_shutdown(self) -> None:
        AppService._apps.clear()
        self.registry.clear()

    async def on_start(self) -> None:
        if type(self).commands: type(self)._load_commands(type(self).commands)
        await super().on_start()

    async def on_started(self) -> None:
        for key, svc in list(AppService._apps.items()):
            if svc is self: continue
            if self._domains and key.split('.')[0] not in self._domains: continue
            await svc.maybe_start()
        for sid, svc in list(AppService._apps.items()):
            if svc.commands: self.logger.info(f'[{sid}] {type(svc).__name__} | commands={svc.commands}')
        if self.registry:
            def _tag(c): return 'Event' if issubclass(c, BaseEvent) else 'Command'
            reg = '\n  '.join(f'{_tag(c):7} {c.alias:20} dest={c.destination or "-"}' for c in self.registry.values())
            self.logger.info(f'registry({len(self.registry)}):\n  {reg}')

    async def emit(self, event: Message):
        await self.dispatch(event)

    def before(self, fn):
        self._before.append(fn); return fn

    def after(self, fn):
        self._after.append(fn); return fn

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

    async def _execute(self, message, runner):
        for fn in self._before:
            short = await fn(message)
            if short is not None:
                if not message.state.done(): message.state.set_result(short)
                return
        await runner(message)
        exc = message.state.exception() if message.state.done() else None
        result = message.state.result() if message.state.done() and not exc else None
        for fn in reversed(self._after):
            await fn(message, result=result, exception=exc)

    @asynccontextmanager
    async def _with_context(self, message):
        app = AppService.resolve_app(message)
        with (_protocol_ctx_stack.push(app.protocol if app else None), _message_ctx_stack.push(message), _app_ctx_stack.push(app)):
            yield

    async def _run_with_context(self, message):
        runner = self._run_gen if message.is_async_gen else self._run
        async with self._with_context(message):
            await self._execute(message, runner)

    async def _run(self, message):
        while True:
            try:
                result = await asyncio.wait_for(message(), timeout=message.expire_time)
                if isinstance(result, Message):  # handoff: chain depth > 5 may degrade perf (stack frames retained)
                    result.trace_id = message.trace_id
                    result.data = {**message.data, **result.data}
                    self.logger.info(f'handoff {message.alias} -> {result.alias}')
                    sub = await self.dispatch(result)
                    result = await sub.state
                if not message.state.done(): message.state.set_result(result)
                break
            except (TimeoutError, HandlerTimeOutError, HandlerMaxRetryError) as e:
                if message.delivery_count:
                    self.logger.info(f'{message.alias} retrying {message.delivery_count}')
                    message.delivery_count -= 1; continue
                if not message.state.done(): message.state.set_exception(e)
                break
            except Exception as e:
                self.logger.exception(e)
                if not message.state.done(): message.state.set_exception(e)
                break

    async def _run_gen(self, message):
        gen = message()
        feedback, pending = None, []
        try:
            while True:
                value = pending.pop() if pending else await asyncio.wait_for(gen.asend(feedback), timeout=message.expire_time)
                if isinstance(value, (list, tuple)):
                    subs = [await self.dispatch(cmd) for cmd in value]
                    feedback = await asyncio.gather(*(sub.state for sub in subs), return_exceptions=True)
                elif isinstance(value, Message):
                    sub = await self.dispatch(value)
                    try:
                        feedback = await sub.state
                    except Exception as exc:
                        try:
                            pending.append(await asyncio.wait_for(gen.athrow(exc), timeout=message.expire_time))
                            feedback = None
                        except StopAsyncIteration:
                            break
                else:
                    feedback = None
                    await message.state.put(value)
        except StopAsyncIteration:
            pass
        except Exception as e:
            self.logger.exception(e)
            if not message.state.done(): message.state.set_exception(e)
        if not message.state.done(): await message.state.put(None)

    async def _process_and_complete(self, message):
        try:
            await self._run_with_context(message)
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

