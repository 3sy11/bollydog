"""ExecuteService: lightweight one-shot command executor without Queue/Exchange."""
from __future__ import annotations

from bollydog.config import DOMAIN
from bollydog.globals import registry
from bollydog.models.base import BaseCommand as Message
from bollydog.models.service import AppService
from bollydog.service.runner import CommandRunnerMixin


class ExecuteService(CommandRunnerMixin, AppService):
    """Inline recursive execution — no Queue, no Exchange, no consumer loop.
    Only starts the target command's AppService + Protocol on demand.
    """
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        await super().on_start()

    async def _submit(self, message: Message):
        _app = registry.resolve_app(message)
        if _app and not _app._started.is_set(): await _app.maybe_start()
        async with self._with_context(message):
            runner = self._run_gen if message.is_async_gen else self._run
            await self._execute(message, runner)
        if message.state.done() and message.state.exception(): raise message.state.exception()
        return message.state.result() if message.state.done() else None

    async def execute(self, message: Message):
        self.logger.info(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias}')
        async with self._with_context(message):
            runner = self._run_gen if message.is_async_gen else self._run
            await self._execute(message, runner)
        return await message.state
