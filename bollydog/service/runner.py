"""CommandRunnerMixin: shared command execution logic for HubService and ExecuteService.

Subclass must implement:
  _submit(message) -> Any   # route sub-command (Queue pipeline vs inline recursive)

self.wait() / self.logger / self._stopped come from mode.Service via MRO.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from bollydog.exception import HandlerTimeOutError, HandlerMaxRetryError
from bollydog.globals import _protocol_ctx_stack, _message_ctx_stack, _app_ctx_stack
from bollydog.models.base import BaseCommand as Message
from bollydog.models.service import AppService


class CommandRunnerMixin:

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._before, self._after = [], []

    async def _submit(self, message: Message) -> Any:
        raise NotImplementedError

    def before(self, fn):
        self._before.append(fn); return fn

    def after(self, fn):
        self._after.append(fn); return fn

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
                if isinstance(result, Message):
                    result.data = {**message.data, **result.data}
                    self.logger.info(f'handoff {message.alias} -> {result.alias}')
                    coro = await self.wait(self._submit(result))
                    if coro.stopped: break
                    result = coro.result
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
                    gather = asyncio.gather(*(self._submit(cmd) for cmd in value), return_exceptions=True)
                    coro = await self.wait(gather)
                    if coro.stopped: break
                    feedback = coro.result
                elif isinstance(value, Message):
                    coro = await self.wait(self._submit(value))
                    if coro.stopped: break
                    try: feedback = coro.result
                    except Exception as exc:
                        try:
                            pending.append(await asyncio.wait_for(gen.athrow(exc), timeout=message.expire_time))
                            feedback = None
                        except StopAsyncIteration: break
                else:
                    feedback = None
                    await message.state.put(value)
        except StopAsyncIteration: pass
        except Exception as e:
            self.logger.exception(e)
            if not message.state.done(): message.state.set_exception(e)
        if not message.state.done(): await message.state.put(None)
