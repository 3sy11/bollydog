"""RegistryService: centralized command/event binding and subscription index."""
from collections import defaultdict
from typing import Dict, Optional, Set, Type

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
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)

    def register(self):
        """Scan all services, populate bindings and subscriptions."""
        for service_key, service in services.items():
            if service.commands_modules:
                self._register_commands(service_key, service)
            if service.subscriber:
                self._register_subscribers(service_key, service)
        self.logger.info(f'bindings({len(self.bindings)}) subscriptions({sum(len(v) for v in self.subscriptions.values())})')

    def _register_commands(self, service_key: str, service: AppService):
        """Scan service command modules, bind each Command/Event via dynamic subclass."""
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

    def _register_subscribers(self, service_key: str, service: AppService):
        """Scan service subscriber config, generate handler Commands, populate subscriptions."""
        for topic, methods in service.subscriber.items():
            methods = [methods] if isinstance(methods, str) else methods
            for method_name in methods:
                bound_method = getattr(service, method_name, None)
                if bound_method is None:
                    raise AttributeError(f"{type(service).__name__} has no method '{method_name}'")
                dest = f'{service_key}.{method_name}'
                async def _call(self, _bm=bound_method): return await _bm(self._source)
                handler_cls = type(method_name, (BaseCommand,), {
                    'destination': dest, 'alias': method_name,
                    'module': type(service).__module__, '_source': None, '__call__': _call,
                })
                self.bindings[dest] = handler_cls
                self.subscriptions[topic].add(dest)

    def subscribe(self, topic: str, dest: str):
        """Runtime subscribe: add topic→dest mapping."""
        self.subscriptions[topic].add(dest)

    def unsubscribe(self, topic: str, dest: str):
        """Runtime unsubscribe: remove topic→dest mapping."""
        self.subscriptions.get(topic, set()).discard(dest)

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
