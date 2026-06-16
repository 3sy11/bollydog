"""RegistryService: centralized command binding index via dynamic subclass."""
from typing import Dict, Optional, Type

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

    def register(self):
        """Scan all services from global services proxy, populate bindings."""
        for service_key, service in services.items():
            _modules = getattr(service, 'commands_modules', None)
            if not _modules: continue
            self._register(service_key, service)
        self.logger.info(f'bindings({len(self.bindings)})')

    def _register(self, service_key: str, service: AppService):
        """Scan service command modules, bind each Command via dynamic subclass."""
        _pkg = type(service).__module__.rsplit('.', 1)[0]
        for module_name in service.commands_modules:
            _fqn = f'{_pkg}.{module_name}' if '.' not in module_name else module_name
            try: _mod = smart_import(_fqn)
            except (ImportError, ModuleNotFoundError, AttributeError): continue
            for _obj in vars(_mod).values():
                if not (isinstance(_obj, type) and issubclass(_obj, BaseCommand) and _obj not in (BaseCommand, BaseEvent)): continue
                if issubclass(_obj, BaseEvent) and 'destination' in _obj.__dict__: continue
                if not issubclass(_obj, BaseEvent) and '__call__' not in _obj.__dict__: continue
                dest = f'{service_key}.{_obj.alias}'
                bound = _obj if _obj.destination else type(_obj.__name__, (_obj,), {'destination': dest})
                self.bindings[dest] = bound

    def resolve(self, destination: str) -> Type[BaseCommand]:
        """Exact destination lookup. Raises KeyError if not found."""
        if destination not in self.bindings: raise KeyError(f"Command '{destination}' not found")
        return self.bindings[destination]

    def resolve_app(self, msg: BaseCommand) -> Optional[AppService]:
        """Resolve owning AppService from message's class-level destination."""
        dest = type(msg).destination
        if not dest: return None
        return services.get('.'.join(dest.split('.')[:2]))

    def get_app(self, service_key: str) -> Optional[AppService]:
        """Lookup AppService by service_key (domain.alias)."""
        return services.get(service_key)
