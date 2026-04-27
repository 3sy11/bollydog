import inspect
import logging
import pathlib
from typing import Any, ClassVar, Dict, List, Type

import mode
from mode.utils.imports import smart_import

from bollydog.models.base import BaseCommand

logger = logging.getLogger(__name__)


class MessageRegistry:
    """Centralized command/event registry, owned by BaseService."""
    def __init__(self):
        self._commands: Dict[str, Type[BaseCommand]] = {}

    def register(self, cmd_cls: Type[BaseCommand]):
        self._commands[f'{cmd_cls.module}.{cmd_cls.alias}'] = cmd_cls

    def resolve(self, name: str) -> Type[BaseCommand]:
        if name in self._commands:
            return self._commands[name]
        matches = {k: v for k, v in self._commands.items() if k.endswith(f'.{name}')}
        if len(matches) == 1: return next(iter(matches.values()))
        if len(matches) > 1: raise KeyError(f"Ambiguous '{name}': {list(matches.keys())}")
        nl = name.lower()
        matches = {k: v for k, v in self._commands.items() if v.alias.lower() == nl}
        if len(matches) == 1: return next(iter(matches.values()))
        if len(matches) > 1: raise KeyError(f"Ambiguous '{name}': {list(matches.keys())}")
        raise KeyError(f"Command '{name}' not found")

    def topics(self) -> Dict[str, Type[BaseCommand]]:
        return {cmd.destination: cmd for cmd in self._commands.values()}

    def resolve_app(self, message, apps: dict):
        """Resolve message destination -> service from apps dict."""
        dest = (message if isinstance(message, type) else type(message)).destination
        if not dest: return None
        key = '.'.join(dest.split('.')[:2])
        return None if key == '_._' else apps.get(key)

    def __len__(self): return len(self._commands)
    def __iter__(self): return iter(self._commands)
    def __bool__(self): return bool(self._commands)
    def items(self): return self._commands.items()
    def values(self): return self._commands.values()
    def keys(self): return self._commands.keys()


class BaseService(mode.Service):
    abstract = True
    domain: ClassVar[str]
    alias: ClassVar[str]
    registry: ClassVar[MessageRegistry] = MessageRegistry()

    def __init__(self, **kwargs):
        super().__init__()

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        super().add_dependency(service)
        return service

    async def on_first_start(self) -> None:
        if False:  # < TODO
            supervisor = mode.OneForOneSupervisor()
            supervisor.add(self)
            await supervisor.start()

    async def crash(self, reason: BaseException) -> None:
        self.logger.error(reason)
        await super(BaseService, self).crash(reason)

    def __init_subclass__(cls, abstract=False, **kwargs):
        super(BaseService, cls).__init_subclass__()
        if 'domain' not in cls.__dict__:
            cls.domain = pathlib.Path(inspect.getmodule(cls).__file__).parent.name
        if 'alias' not in cls.__dict__:
            cls.alias = cls.__name__

    def __repr__(self) -> str:
        return f"<{self._repr_name()}: {self.state}: {id(self)}>"

    def _log_mundane(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log.log(self._mundane_level, msg, stacklevel=3, *args, **kwargs)  # < 3


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
    router_mapping: ClassVar[dict] = {}
    commands: ClassVar[List[str]] = []
    subscriber: ClassVar[dict] = {}
    protocol = None

    def __init__(self, router_mapping=None, subscribe=None, **kwargs):
        super().__init__(**kwargs)
        self.router_mapping = {**self.__class__.router_mapping, **(router_mapping or {})} if router_mapping is not None else self.__class__.router_mapping
        self.subscriber = {**self.__class__.subscriber, **(subscribe or {})} if subscribe is not None else self.__class__.subscriber

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        from bollydog.models.protocol import Protocol
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()

    @classmethod
    def _load_commands(cls, modules: List[str]):
        from bollydog.models.base import BaseEvent
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
        commands = conf.pop('commands', None)
        router_mapping = conf.pop('router_mapping', None)
        subscriber = conf.pop('subscriber', None)
        protocol_conf = conf.pop('protocol', None)
        merged_commands = list({*(cls.commands or []), *(commands or [])})
        merged_sub = {**cls.subscriber, **(subscriber or {})} if subscriber else None
        if merged_sub:
            for topic, handler in list(merged_sub.items()):
                if isinstance(handler, str):
                    merged_sub[topic] = smart_import(handler)
        cls._load_commands(merged_commands)
        logger.debug(f'create_from {cls.__name__}')
        svc = cls(router_mapping=router_mapping, subscribe=merged_sub, **conf)
        if protocol_conf:
            proto = _build_protocol(protocol_conf)
            svc.add_dependency(proto)
        return svc
