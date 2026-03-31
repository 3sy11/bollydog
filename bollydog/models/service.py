import inspect
import logging
import pathlib
from typing import Any, ClassVar, List

import mode
from mode.utils.imports import smart_import

logger = logging.getLogger(__name__)


class BaseService(mode.Service):
    abstract = True
    domain: ClassVar[str]
    alias: ClassVar[str]

    def __init__(self, **kwargs):
        super().__init__()

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        super().add_dependency(service)
        return service

    async def on_first_start(self) -> None:
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


class AppService(BaseService, abstract=True):
    router_mapping: ClassVar[dict] = {}
    commands: ClassVar[List[str]] = []
    subscribe: ClassVar[dict] = {}

    async def on_first_start(self) -> None:
        await super(AppService, self).on_first_start()

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()

    def __init__(self, protocol=None, router_mapping=None, subscribe=None, **kwargs):
        super().__init__(**kwargs)
        self.protocol = protocol
        self.router_mapping = router_mapping if router_mapping is not None else self.__class__.router_mapping
        self.subscribe = subscribe if subscribe is not None else self.__class__.subscribe

    @classmethod
    def _load_commands(cls, modules: List[str]):
        from bollydog.models.base import BaseCommand
        pkg = cls.__module__.rsplit('.', 1)[0]
        dest_prefix = f'{cls.domain}.{cls.alias}'
        for name in modules:
            fqn = f'{pkg}.{name}' if '.' not in name else name
            before = set(BaseCommand._registry.keys())
            try:
                smart_import(fqn)
            except (ImportError, ModuleNotFoundError, AttributeError):
                continue
            for key in set(BaseCommand._registry.keys()) - before:
                cmd_cls = BaseCommand._registry[key]
                if str(cmd_cls.destination).startswith('_._'):
                    cmd_cls.destination = f'{dest_prefix}.{cmd_cls.alias}'

    @classmethod
    def create_from(cls, protocol=None, router_mapping=None, commands=None, subscribe=None, **kwargs):
        cls._load_commands(commands if commands is not None else cls.commands)
        logger.debug(f'create_from {cls.__name__} {protocol}')
        if protocol:
            protocol = protocol['module'](**protocol)
        app_service = cls(protocol=protocol, router_mapping=router_mapping, subscribe=subscribe, **kwargs)
        if protocol:
            app_service.add_dependency(protocol)
        return app_service
