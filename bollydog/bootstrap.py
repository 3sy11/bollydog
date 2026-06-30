"""Bootstrap: unified Worker for bollydog framework.

Exposes entry method for CLI:
  run()              -> eager start all services, daemon mode
  run(msg)           -> execute single command, then stop
"""
import signal
import tomllib
from functools import cached_property
from typing import TYPE_CHECKING, Optional

import mode
from mode.utils.imports import smart_import

from bollydog.config import SERVICE_CONFIG
from bollydog.globals import _hub_ctx_stack, _session_ctx_stack, _services_ctx_stack, _registry_ctx_stack
from bollydog.models.base import BaseCommand as Message

if TYPE_CHECKING:
    from bollydog.service.app import HubService
    from bollydog.service.executor import ExecuteService
    from bollydog.service.registry import RegistryService
    from bollydog.service.session import Session


class BollydogServices(dict):
    """Dict subclass with typed property accessors for framework services."""
    @property
    def registry(self) -> Optional['RegistryService']: return self.get('bollydog.RegistryService')
    @property
    def session(self) -> Optional['Session']: return self.get('bollydog.Session')
    @property
    def hub(self) -> Optional['HubService']: return self.get('bollydog.HubService')
    @property
    def executor(self) -> Optional['ExecuteService']: return self.get('bollydog.ExecuteService')


class Bootstrap(mode.Worker):
    supervisor = mode.OneForOneSupervisor()

    def __init__(self, config: str = None, **kwargs):
        self._config = config
        self._message: Optional[Message] = None
        self.services = self._build_services()
        super().__init__(*self.services.values(), **kwargs)
        _services_ctx_stack.push_without_automatic_cleanup(self.services)
        if self.services.registry:
            _registry_ctx_stack.push_without_automatic_cleanup(self.services.registry)
            self.services.registry.register()
        if self.services.session:
            _session_ctx_stack.push_without_automatic_cleanup(self.services.session)
        if self.services.hub:
            _hub_ctx_stack.push_without_automatic_cleanup(self.services.hub)

    def on_init_dependencies(self):
        return []

    @cached_property
    def config(self) -> dict:
        merged = dict(SERVICE_CONFIG)
        if self._config:
            with open(self._config, 'rb') as f:
                merged.update(tomllib.load(f))
        return merged

    def _build_services(self) -> 'BollydogServices':
        services = BollydogServices()
        for name, conf in self.config.items():
            conf = dict(conf)
            module = conf.pop('module', name)
            _service = smart_import(module).create_from(**conf)
            key = f'{_service.domain}.{_service.alias}'
            services[key] = _service
        for _service in services.values():
            if (isinstance(_service.depends, (list, tuple)) and _service.depends
                    and isinstance(_service.depends[0], str)):
                _resolved = {}
                for _depend in _service.depends:
                    _dep = services.get(_depend)
                    if _dep is None:
                        raise ValueError(f"depends '{_depend}' not found for {_service.domain}.{_service.alias}")
                    _service.add_dependency(_dep)
                    _resolved[_depend] = _dep
                _service.depends = _resolved
        return services

    # --- entry ---

    def run(self, message: Message = None, timeout: int = 300):
        if message:
            self._message = message
            if timeout: self._message.expire_time = min(self._message.expire_time, timeout)
        self.execute_from_commandline()

    # --- lifecycle ---

    async def on_first_start(self) -> None:
        self.install_signal_handlers()
        await super().on_first_start()

    async def on_started(self) -> None:
        if self._message:
            await self.services.executor.maybe_start()
            try: await self.services.executor.execute(self._message)
            except Exception as e: self.logger.exception(e)
            finally: await self.stop()
        else:
            for service in self.services.values():
                await service.maybe_start()
            self._log_bindings()

    def _log_bindings(self):
        if not self.services.registry: return
        commands = self.services.registry.commands
        if commands:
            _lines = '\n  '.join(f'{cmd_cls.alias:<20} -> {destination}' for destination, cmd_cls in commands.items())
            self.logger.info(f'commands({len(commands)}):\n  {_lines}')
        subs = self.services.registry.subscribers
        if subs:
            _lines = '\n  '.join(f'{t} -> [{", ".join(dests)}]' for t, dests in subs.items())
            self.logger.info(f'subscribers({sum(len(v) for v in subs.values())}):\n  {_lines}')

    async def on_shutdown(self) -> None:
        self.services.clear()

    def on_worker_shutdown(self) -> None:
        pass

    def stop_and_shutdown(self) -> None:
        super().stop_and_shutdown()

    def _on_sigint(self) -> None:
        self.logger.info('-EXIT-')
        self._schedule_shutdown(signal.SIGINT)
