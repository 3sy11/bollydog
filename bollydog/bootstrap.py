"""Bootstrap: unified Worker for bollydog framework.

Exposes two entry methods for CLI:
  start_all()        -> eager start all services, daemon mode
  run_once(msg)      -> execute single command, then stop
"""
import json
import logging
import signal
import tomllib
from functools import cached_property
from typing import Optional

import mode
from mode.utils.imports import smart_import

from bollydog.config import DEFAULT_SERVICES
from bollydog.globals import _hub_ctx_stack, _session_ctx_stack, _services_ctx_stack
from bollydog.models.base import BaseCommand as Message, BaseEvent, BaseService


class Bootstrap(mode.Worker):
    supervisor = mode.OneForOneSupervisor()

    def __init__(self, config: str = None, **kwargs):
        self._config_path = config
        self._message: Optional[Message] = None
        _services = self._build_services()
        super().__init__(*_services.values(), **kwargs)
        self.services = _services

    def on_init_dependencies(self):
        return []

    @cached_property
    def config(self) -> dict:
        """Merged config: DEFAULT_SERVICES + user TOML. Mode-agnostic."""
        merged = dict(DEFAULT_SERVICES)
        if self._config_path:
            with open(self._config_path, 'rb') as f:
                merged.update(tomllib.load(f))
        return merged

    def _build_services(self) -> dict:
        """Iterate self.config, create all service instances, resolve depends, load commands."""
        service_dict = {}
        for node_name, node_conf in self.config.items():
            node_conf = dict(node_conf)
            module = node_conf.pop('module', node_name)
            service = smart_import(module).create_from(**node_conf)
            service_dict[f'{service.domain}.{service.alias}'] = service
        for service in service_dict.values():
            if isinstance(service.depends, (list, tuple)) and service.depends and isinstance(service.depends[0], str):
                resolved = []
                for dep_key in service.depends:
                    dependency = service_dict.get(dep_key)
                    if dependency is None:
                        raise ValueError(f"depends '{dep_key}' not found for {service.domain}.{service.alias}")
                    service.add_dependency(dependency)
                    resolved.append(dependency)
                service.depends = resolved
        for service in service_dict.values():
            if type(service).commands:
                type(service)._load_commands(type(service).commands)
        return service_dict

    # --- entry methods for CLI ---

    def start_all(self):
        """Service mode: eager start all services, enter daemon loop."""
        self.execute_from_commandline()

    def run_once(self, message: Message, timeout: int = 300):
        """Execute mode: run single command then stop."""
        self._message = message
        if timeout:
            self._message.expire_time = min(self._message.expire_time, timeout)
        self.execute_from_commandline()

    # --- lifecycle hooks ---

    async def on_first_start(self) -> None:
        self.install_signal_handlers()
        self.exit_stack.enter_context(_services_ctx_stack.push(self.services))
        session = self.services.get('bollydog.Session')
        if session:
            self.exit_stack.enter_context(_session_ctx_stack.push(session))
        hub = self.services.get('bollydog.HubService')
        if hub:
            self.exit_stack.enter_context(_hub_ctx_stack.push(hub))
        await super().on_first_start()

    async def on_started(self) -> None:
        if self._message:
            executor = self.services['bollydog.ExecuteService']
            await executor.maybe_start()
            try:
                await executor.execute(self._message)
            except Exception as e:
                self.logger.exception(e)
            finally:
                await self.stop()
        else:
            for svc in self.services.values():
                await svc.maybe_start()
            self._log_registry()

    def _log_registry(self):
        for sid, svc in self.services.items():
            if svc.commands:
                self.logger.info(f'[{sid}] {type(svc).__name__} | commands={svc.commands}')
        registry = BaseService.registry
        if registry:
            def _tag(c): return 'Event' if issubclass(c, BaseEvent) else 'Command'
            reg = '\n  '.join(f'{_tag(c):7} {c.alias:20} dest={c.destination or "-"}' for c in registry.values())
            self.logger.info(f'registry({len(registry)}):\n  {reg}')

    async def on_shutdown(self) -> None:
        self.services.clear()
        BaseService.registry.clear()

    def on_worker_shutdown(self) -> None:
        pass

    def stop_and_shutdown(self) -> None:
        super().stop_and_shutdown()

    def _on_sigint(self) -> None:
        self.logger.info('-EXIT-')
        self._schedule_shutdown(signal.SIGINT)
