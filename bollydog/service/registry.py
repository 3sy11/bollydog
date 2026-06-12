"""RegistryService: centralized command binding index."""
from typing import Dict, List, Optional, Type

from bollydog.config import DOMAIN
from bollydog.globals import services
from bollydog.models.base import BaseCommand, BaseEvent
from bollydog.models.service import AppService
from mode.utils.imports import smart_import


class RegistryService(AppService):
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bindings: Dict[str, Type[BaseCommand]] = {}
        self._cmd_alias_index: Dict[str, Optional[str]] = {}

    def register(self):
        """Scan all services from global services proxy, populate bindings."""
        for service_key, service in services.items():
            _modules = getattr(service, 'commands_modules', None)
            if not _modules: continue
            self._register(service_key, service)
        self._build_cmd_alias_index()
        self.logger.info(f'bindings({len(self.bindings)}) cmd_aliases({len(self._cmd_alias_index)})')

    def _register(self, service_key: str, service: AppService):
        """Scan a single service's command modules and add to bindings."""
        _pkg = type(service).__module__.rsplit('.', 1)[0]
        for module_name in service.commands_modules:
            _fqn = f'{_pkg}.{module_name}' if '.' not in module_name else module_name
            try: _mod = smart_import(_fqn)
            except (ImportError, ModuleNotFoundError, AttributeError): continue
            for _obj in vars(_mod).values():
                if (isinstance(_obj, type) and issubclass(_obj, BaseCommand)
                        and _obj is not BaseCommand and _obj is not BaseEvent
                        and not issubclass(_obj, BaseEvent)
                        and '__call__' in _obj.__dict__):
                    destination = f'{service_key}.{_obj.alias}'
                    self.bindings[destination] = _obj

    def _build_cmd_alias_index(self):
        """Pre-build cmd_alias -> destination index. Log ambiguities at startup."""
        _grouped: Dict[str, List[str]] = {}
        for destination, cmd_cls in self.bindings.items():
            _grouped.setdefault(cmd_cls.alias, []).append(destination)
        for cmd_alias, destinations in _grouped.items():
            if len(destinations) == 1:
                self._cmd_alias_index[cmd_alias] = destinations[0]
            else:
                self._cmd_alias_index[cmd_alias] = None
                self.logger.warning(f'ambiguous cmd_alias "{cmd_alias}" -> {destinations}, sub-commands must set destination explicitly')

    def resolve(self, destination: str) -> Type[BaseCommand]:
        """Exact destination lookup. Raises KeyError if not found."""
        if destination not in self.bindings:
            raise KeyError(f"Command '{destination}' not found")
        return self.bindings[destination]

    def instantiate(self, destination: str, **kwargs) -> BaseCommand:
        """Create command instance with destination set as instance attribute."""
        cmd_cls = self.resolve(destination)
        msg = cmd_cls(**kwargs)
        msg.destination = destination
        return msg

    def resolve_app(self, msg: BaseCommand) -> Optional[AppService]:
        """Resolve owning AppService for a command instance."""
        destination = msg.destination
        if not destination:
            destination = self._lookup_by_cmd_alias(msg.alias)
            if destination: msg.destination = destination
        if not destination: return None
        service_key = '.'.join(destination.split('.')[:2])
        return services.get(service_key)

    def _lookup_by_cmd_alias(self, cmd_alias: str) -> Optional[str]:
        """O(1) lookup from pre-built index. Raises if ambiguous."""
        if cmd_alias not in self._cmd_alias_index:
            return None
        destination = self._cmd_alias_index[cmd_alias]
        if destination is None:
            raise KeyError(f"cmd_alias '{cmd_alias}' is ambiguous (multiple services). Set message.destination explicitly. See startup warnings.")
        return destination
