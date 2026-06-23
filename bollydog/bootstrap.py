"""Bootstrap: unified Worker for bollydog framework.

Exposes two entry methods for CLI:
  start_all()        -> eager start all services, daemon mode
  run_once(msg)      -> execute single command, then stop
"""
import signal
import tomllib
from functools import cached_property
from typing import Optional

import mode
from mode.utils.imports import smart_import

from bollydog.config import DEFAULT_SERVICES
from bollydog.globals import _hub_ctx_stack, _session_ctx_stack, _services_ctx_stack, _registry_ctx_stack
from bollydog.models.base import BaseCommand as Message


class Bootstrap(mode.Worker):
    supervisor = mode.OneForOneSupervisor()

    def __init__(self, config: str = None, **kwargs):
        self._config_path = config
        self._message: Optional[Message] = None
        _services = self._build_services()
        super().__init__(*_services.values(), **kwargs)
        self.services = _services
        self.registry_service = self.services.get('bollydog.RegistryService')
        self.session_service = self.services.get('bollydog.Session')
        self.hub_service = self.services.get('bollydog.HubService')
        self.executor_service = self.services.get('bollydog.ExecuteService')
        _services_ctx_stack.push_without_automatic_cleanup(self.services)
        if self.registry_service:
            _registry_ctx_stack.push_without_automatic_cleanup(self.registry_service)
            self.registry_service.register()

    def on_init_dependencies(self):
        return []

    @cached_property
    def config(self) -> dict:
        merged = dict(DEFAULT_SERVICES)
        if self._config_path:
            with open(self._config_path, 'rb') as f:
                merged.update(tomllib.load(f))
        return merged

    def _build_services(self) -> dict:
        service_dict = {}
        for node_name, node_conf in self.config.items():
            node_conf = dict(node_conf)
            module = node_conf.pop('module', node_name)
            service = smart_import(module).create_from(**node_conf)
            service_key = f'{service.domain}.{service.alias}'
            service_dict[service_key] = service
        for service in service_dict.values():
            if (isinstance(service.depends, (list, tuple)) and service.depends
                    and isinstance(service.depends[0], str)):
                _resolved = {}
                for dep_key in service.depends:
                    _dep = service_dict.get(dep_key)
                    if _dep is None:
                        raise ValueError(f"depends '{dep_key}' not found for {service.domain}.{service.alias}")
                    service.add_dependency(_dep)
                    _resolved[dep_key] = _dep
                service.depends = _resolved
        return service_dict

    # --- entry methods ---

    def start_all(self):
        self.execute_from_commandline()

    def run_once(self, message: Message, timeout: int = 300):
        self._message = message
        if timeout:
            self._message.expire_time = min(self._message.expire_time, timeout)
        self.execute_from_commandline()

    # --- lifecycle ---

    async def on_first_start(self) -> None:
        self.install_signal_handlers()
        if self.session_service:
            self.exit_stack.enter_context(_session_ctx_stack.push(self.session_service))
        if self.hub_service:
            self.exit_stack.enter_context(_hub_ctx_stack.push(self.hub_service))
        await super().on_first_start()

    async def on_started(self) -> None:
        if self._message:
            await self.executor_service.maybe_start()
            try: await self.executor_service.execute(self._message)
            except Exception as e: self.logger.exception(e)
            finally: await self.stop()
        else:
            for service in self.services.values():
                await service.maybe_start()
            self._log_bindings()

    def _log_bindings(self):
        if not self.registry_service: return
        bindings = self.registry_service.bindings
        if bindings:
            _lines = '\n  '.join(f'{cmd_cls.alias:<20} -> {destination}' for destination, cmd_cls in bindings.items())
            self.logger.info(f'bindings({len(bindings)}):\n  {_lines}')
        subs = self.registry_service.subscriptions
        if subs:
            _lines = '\n  '.join(f'{t} -> [{", ".join(dests)}]' for t, dests in subs.items())
            self.logger.info(f'subscriptions({sum(len(v) for v in subs.values())}):\n  {_lines}')

    async def on_shutdown(self) -> None:
        self.services.clear()

    def on_worker_shutdown(self) -> None:
        pass

    def stop_and_shutdown(self) -> None:
        super().stop_and_shutdown()

    def _on_sigint(self) -> None:
        self.logger.info('-EXIT-')
        self._schedule_shutdown(signal.SIGINT)
