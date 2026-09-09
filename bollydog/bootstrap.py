"""Bootstrap: unified Worker for bollydog framework.

Exposes entry method for CLI:
  run()              -> eager start all services, daemon mode
  run(msg)           -> execute single command, then stop
"""
import inspect
import signal
import tomllib
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import mode
from mode.utils.imports import smart_import

from bollydog.config import (
    ENTRYPOINT_HTTP_ENABLED,
    ENTRYPOINT_WS_ENABLED,
    ENTRYPOINT_UDS_ENABLED,
)
from bollydog.globals import _hub_ctx_stack, _session_ctx_stack, _services_ctx_stack, _registry_ctx_stack
from bollydog.models.base import BaseCommand, BaseEvent
from bollydog.models.service import AppService

if TYPE_CHECKING:
    from bollydog.service.app import HubService
    from bollydog.service.exchange import Exchange
    from bollydog.service.executor import ExecuteService
    from bollydog.service.registry import RegistryService
    from bollydog.service.session import Session


def _walk_modules(key: str, service: AppService):
    """Yield (destination, class) for every concrete Command/Event declared in
    the service's command modules.

    Classes without their own destination get a dynamic subclass carrying it, so
    the same class can be owned by several service instances.
    """
    _pkg = type(service).__module__.rsplit('.', 1)[0]
    for module_name in service.commands:
        _fqn = f'{_pkg}.{module_name}' if '.' not in module_name else module_name
        try: _mod = smart_import(_fqn)
        except (ImportError, ModuleNotFoundError, AttributeError): continue
        for _obj in vars(_mod).values():
            if not (isinstance(_obj, type) and issubclass(_obj, BaseCommand)): continue
            # BaseCommand.__call__ is abstract, so a Command that never defines
            # one is an unfinished intermediate. BaseEvent's is concrete, so
            # notification-only Events survive this filter.
            if _obj in (BaseCommand, BaseEvent) or inspect.isabstract(_obj): continue
            dest = _obj.destination or f'{key}.{_obj.alias}'
            yield dest, _obj if _obj.destination else type(_obj.__name__, (_obj,), {'destination': dest})


class BollydogServices(dict):
    """Dict subclass with typed property accessors for framework services."""
    @property
    def registry(self) -> Optional['RegistryService']: return self.get('bollydog.RegistryService')
    @property
    def exchange(self) -> Optional['Exchange']: return self.get('bollydog.Exchange')
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
        self._message: Optional[BaseCommand] = None
        _services = self._build_services()
        _app_services = BollydogServices({
            k: v for k, v in _services.items()
            if isinstance(v, AppService)
        })
        super().__init__(*_app_services.values(), **kwargs)
        self.services = _app_services
        _services_ctx_stack.push_without_automatic_cleanup(self.services)
        _registry_ctx_stack.push_without_automatic_cleanup(self.services.registry)
        _session_ctx_stack.push_without_automatic_cleanup(self.services.session)
        _hub_ctx_stack.push_without_automatic_cleanup(self.services.hub)

    def on_init_dependencies(self):
        return []

    @cached_property
    def config(self) -> dict:
        # TODO: ENABLED flags gate entrypoint TOML loading, but if app TOML
        #  re-declares the same entrypoint key, the service will be created
        #  regardless of ENABLED=0 — need a filtering step after merge.
        merged = {}
        base = Path(__file__).parent
        with open(base / 'service' / 'config.toml', 'rb') as f:
            merged.update(tomllib.load(f))
        if ENTRYPOINT_HTTP_ENABLED:
            with open(base / 'entrypoint' / 'http' / 'config.toml', 'rb') as f:
                merged.update(tomllib.load(f))
        if ENTRYPOINT_WS_ENABLED:
            with open(base / 'entrypoint' / 'websocket' / 'config.toml', 'rb') as f:
                merged.update(tomllib.load(f))
        if ENTRYPOINT_UDS_ENABLED:
            with open(base / 'entrypoint' / 'uds' / 'config.toml', 'rb') as f:
                merged.update(tomllib.load(f))
        if self._config:
            with open(self._config, 'rb') as f:
                merged.update(tomllib.load(f))
        return merged

    def _build_services(self) -> dict:
        """Two-phase build: instantiate everything, then wire it up."""
        config = self.config
        _services = {}

        # Phase 1: create all instances — nothing may reference another service yet
        for key, entry in config.items():
            conf = dict(entry)
            module_path = conf.pop('module', None)
            if not module_path:
                raise ValueError(f"TOML entry '{key}' missing 'module' field")

            cls = smart_import(module_path)
            domain, alias = key.rsplit('.', 1) if '.' in key else (cls.domain, key)

            if key in _services:
                raise ValueError(f"duplicate TOML key: '{key}'")

            instance = cls.create_from(**conf)
            instance.alias = alias
            instance.domain = domain
            _services[key] = instance

        # Phase 2: wire protocol, depends, commands and events. All four only need
        # Phase 1 finished; none of them depends on the others, so one pass does it.
        _registry = _services.get('bollydog.RegistryService')
        _exchange = _services.get('bollydog.Exchange')
        for key, instance in _services.items():
            if ref := getattr(instance, '_protocol', None):
                proto = _services.get(ref)
                if proto is None:
                    raise ValueError(f"protocol '{ref}' not found for '{key}'")
                instance.add_dependency(proto)

            if raw := getattr(instance, '_depends', None):
                resolved = {}
                for dep_ref in raw:
                    dep = _services.get(dep_ref)
                    if dep is None:
                        raise ValueError(f"depends '{dep_ref}' not found for '{key}'")
                    instance.add_dependency(dep)
                    resolved[dep_ref] = dep
                instance.depends = resolved

            if not isinstance(instance, AppService):
                continue

            for dest, cls in _walk_modules(key, instance):
                if issubclass(cls, BaseEvent):
                    _exchange.add_event(dest, cls)
                else:
                    _registry.add_command(dest, cls)

            # subscribe aliases an already-registered Event class onto extra topics
            for topic, names in instance.subscribe.items():
                for name in ([names] if isinstance(names, str) else names):
                    dest = name if '.' in name else f'{key}.{name}'
                    try:
                        _exchange.add_event(topic, _exchange.resolve(dest))
                    except KeyError:
                        raise ValueError(
                            f"'{key}' subscribes '{topic}' to unknown Event '{dest}' — "
                            f"declare it in one of the modules listed in commands"
                        ) from None

        return _services

    # --- entry ---

    def run(self, message=None, timeout: int = 300):
        self._message = message
        self._timeout = timeout
        self.execute_from_commandline()

    # --- lifecycle ---

    async def on_first_start(self) -> None:
        self.install_signal_handlers()
        await super().on_first_start()

    async def on_started(self) -> None:
        if callable(self._message): self._message = self._message()
        if self._message:
            if self._timeout: self._message.expire_time = min(self._message.expire_time, self._timeout)
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
        commands = self.services.registry.all_commands()
        if commands:
            _lines = '\n  '.join(f'{cmd_cls.alias:<20} -> {destination}' for destination, cmd_cls in commands.items())
            self.logger.info(f'commands({len(commands)}):\n  {_lines}')

    async def on_shutdown(self) -> None:
        for stack in (_hub_ctx_stack, _registry_ctx_stack, _session_ctx_stack, _services_ctx_stack):
            if stack.top is not None:
                stack.pop()
        self.services.clear()

    def on_worker_shutdown(self) -> None:
        pass

    def stop_and_shutdown(self) -> None:
        super().stop_and_shutdown()

    def _on_sigint(self) -> None:
        self.logger.info('-EXIT-')
        self._schedule_shutdown(signal.SIGINT)
