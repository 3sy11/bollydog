import logging
from typing import ClassVar, Dict, List, Optional

from mode.utils.imports import smart_import

from bollydog.models.base import BaseCommand, BaseEvent, BaseService, MessageRegistry
from bollydog.models.protocol import Protocol

logger = logging.getLogger(__name__)

# re-export for from bollydog.models.service import BaseService, AppService, MessageRegistry
__all__ = ['MessageRegistry', 'BaseService', 'AppService', '_build_protocol']


def _build_protocol(conf: dict):
    """Recursively build protocol chain from TOML nested dict."""
    conf = dict(conf)
    module = conf.pop('module')
    inner_conf = conf.pop('protocol', None)
    cls = smart_import(module)
    proto = cls(**conf)
    if inner_conf:
        inner = _build_protocol(inner_conf)
        proto.add_dependency(inner)
    return proto


class AppService(BaseService, abstract=True):
    _apps: ClassVar[Dict[str, 'AppService']] = {}
    protocol = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._depends: list = []
        AppService._apps[f'{self.domain}.{self.alias}'] = self

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    @classmethod
    def resolve_app(cls, message) -> Optional['AppService']:
        dest = (message if isinstance(message, type) else type(message)).destination
        if not dest: return None
        key = '.'.join(dest.split('.')[:2])
        return None if key == '_._' else cls._apps.get(key)

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()

    @classmethod
    def _load_commands(cls, modules: List[str]):
        pkg = cls.__module__.rsplit('.', 1)[0]
        dest_prefix = f'{cls.domain}.{cls.alias}'
        for name in modules:
            fqn = f'{pkg}.{name}' if '.' not in name else name
            try:
                mod = smart_import(fqn)
            except (ImportError, ModuleNotFoundError, AttributeError):
                continue
            for obj in vars(mod).values():
                if (isinstance(obj, type) and issubclass(obj, BaseCommand)
                        and obj is not BaseCommand and obj is not BaseEvent
                        and '__call__' in obj.__dict__):
                    if str(obj.destination).startswith('_._'):
                        obj.destination = f'{dest_prefix}.{obj.alias}'
                    cls.registry.register(obj)

    @classmethod
    def create_from(cls, **conf):
        commands, router_mapping, subscriber, depends, protocol_conf = (
            conf.pop(k, None) for k in ('commands', 'router_mapping', 'subscriber', 'depends', 'protocol'))
        if commands: cls.commands = [*{*(cls.commands or []), *commands}]
        if router_mapping: cls.router_mapping = {**(cls.router_mapping or {}), **router_mapping}
        if subscriber: cls.subscriber = {**(cls.subscriber or {}), **{t: smart_import(h) if isinstance(h, str) else h for t, h in subscriber.items()}}
        logger.debug(f'create_from {cls.__name__}')
        svc = cls(**conf)
        if protocol_conf: svc.add_dependency(_build_protocol(protocol_conf))
        svc._depends = list(depends) if depends else []
        return svc
