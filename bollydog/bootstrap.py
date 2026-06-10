"""Bootstrap: unified root service for both service and execute modes.

service mode: Bootstrap(hub, daemon=True)  -> execute_from_commandline() -> wait_until_stopped
execute mode: Bootstrap(executor)          -> run_once(msg) -> execute -> stop -> shutdown_loop
"""
import json
import logging
import signal
from typing import Iterable, Optional

import mode

from bollydog.globals import _hub_ctx_stack, _session_ctx_stack
from bollydog.models.base import BaseCommand as Message, BaseEvent, BaseService


class Bootstrap(mode.Worker):
    supervisor = mode.OneForOneSupervisor()
    _message: Optional[Message] = None
    _domains: Optional[set] = None

    def __init__(self, *services, apps: dict = None, **kwargs):
        self.apps = apps or {}
        super().__init__(*services, **kwargs)

    def on_init_dependencies(self) -> Iterable[mode.ServiceT]:
        return self.services

    async def on_first_start(self) -> None:
        self.install_signal_handlers()
        session = self.apps.get('bollydog.Session')
        if session: self.exit_stack.enter_context(_session_ctx_stack.push(session))
        hub = self.apps.get('bollydog.HubService')
        if hub: self.exit_stack.enter_context(_hub_ctx_stack.push(hub))
        await super(Bootstrap, self).on_first_start()

    async def on_start(self) -> None:
        pass

    async def on_started(self) -> None:
        for key, svc in list(self.apps.items()):
            if svc in (s for s in self.services): continue
            if self._domains and key.split('.')[0] not in self._domains: continue
            await svc.maybe_start()
        self._log_registry()
        if self._message:
            try:
                root_svc = next(iter(self.services))
                await root_svc.execute(self._message)
                logging.info(json.dumps(self._message.model_dump(), ensure_ascii=False))
            except Exception as e:
                logging.exception(e)
            finally:
                await self.stop()
        else:
            await super(Bootstrap, self).on_started()

    def _log_registry(self):
        for sid, svc in list(self.apps.items()):
            if svc.commands: self.logger.info(f'[{sid}] {type(svc).__name__} | commands={svc.commands}')
        registry = BaseService.registry
        if registry:
            def _tag(c): return 'Event' if issubclass(c, BaseEvent) else 'Command'
            reg = '\n  '.join(f'{_tag(c):7} {c.alias:20} dest={c.destination or "-"}' for c in registry.values())
            self.logger.info(f'registry({len(registry)}):\n  {reg}')

    async def on_shutdown(self) -> None:
        self.apps.clear()
        BaseService.registry.clear()

    def run_once(self, message: Message, timeout: int = 300):
        """Execute mode entry. Sets message.expire_time from CLI timeout, then runs full Worker lifecycle."""
        self._message = message
        if timeout: self._message.expire_time = min(self._message.expire_time, timeout)
        self.execute_from_commandline()

    def on_worker_shutdown(self) -> None:
        pass

    def stop_and_shutdown(self) -> None:
        super(Bootstrap, self).stop_and_shutdown()

    def _on_sigint(self) -> None:
        self.logger.info('-EXIT- -EXIT- -EXIT- -EXIT- -EXIT- -EXIT-')
        self._schedule_shutdown(signal.SIGINT)
