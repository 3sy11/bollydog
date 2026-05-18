import logging
from typing import ClassVar, Dict, List, Optional

from mode.utils.imports import smart_import

from bollydog.models.base import BaseCommand, BaseEvent, BaseService
from bollydog.models.protocol import Protocol

logger = logging.getLogger(__name__)

__all__ = ['BaseService', 'AppService', '_build_protocol']


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
        key = f'{self.domain}.{self.alias}'
        if key in AppService._apps: logger.warning(f'AppService._apps overwrite: {key}')
        AppService._apps[key] = self

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

    @classmethod
    def _derive(cls, alias: str = None):
        """Create derived subclass with isolated ClassVars to prevent pollution."""
        return type(cls.__name__, (cls,), {
            '__module__': cls.__module__, 'domain': cls.domain,
            'alias': alias or cls.alias,
            'commands': list(cls.commands), 'router_mapping': dict(cls.router_mapping),
            'subscriber': dict(cls.subscriber), 'depends': dict(cls.depends),
        })

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
            try: mod = smart_import(fqn)
            except (ImportError, ModuleNotFoundError, AttributeError): continue
            for obj in vars(mod).values():
                if (isinstance(obj, type) and issubclass(obj, BaseCommand)
                        and obj is not BaseCommand and obj is not BaseEvent
                        and '__call__' in obj.__dict__):
                    derived = obj._derive(dest_prefix) if str(obj.destination).startswith('_._') else obj
                    cls.registry[derived.destination] = derived

    @classmethod
    def create_from(cls, **conf):
        alias = conf.pop('alias', None)
        derived = cls._derive(alias)
        commands, router_mapping, subscriber, depends, protocol_conf = (
            conf.pop(k, None) for k in ('commands', 'router_mapping', 'subscriber', 'depends', 'protocol'))
        if commands: derived.commands = [*{*derived.commands, *commands}]
        if router_mapping: derived.router_mapping = {**derived.router_mapping, **router_mapping}
        if subscriber: derived.subscriber = {**derived.subscriber, **subscriber}
        if depends:
            new_deps = {k: None for k in depends} if isinstance(depends, list) else depends
            derived.depends = {**derived.depends, **new_deps}
        logger.debug(f'create_from {derived.__name__} alias={derived.alias}')
        svc = derived(**conf)
        svc.config = conf
        if protocol_conf: svc.add_dependency(_build_protocol(protocol_conf))
        return svc
