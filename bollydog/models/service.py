import logging
from typing import ClassVar, List

from mode.utils.imports import smart_import

from bollydog.models.base import BaseCommand, BaseService
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
    commands: ClassVar[List[str]] = []
    router_mapping: ClassVar[dict] = {}
    subscriber: ClassVar[dict] = {}
    depends: ClassVar[list] = []
    protocol = None

    def __init__(self, commands_modules=None, router_mapping=None,
                 subscriber=None, depends=None, **kwargs):
        super().__init__(**kwargs)
        self.commands_modules = commands_modules or []
        self.router_mapping = router_mapping or {}
        self.subscriber = subscriber or {}
        self.depends = depends or []

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    @classmethod
    def create_from(cls, **conf):
        svc_alias = conf.pop('alias', None)
        commands = [*{*(cls.commands or []), *(conf.pop('commands', None) or [])}]
        router_mapping = {**(cls.router_mapping or {}), **(conf.pop('router_mapping', None) or {})}
        subscriber = {**(cls.subscriber or {}), **(conf.pop('subscriber', None) or {})}
        depends = [*{*(cls.depends or []), *(conf.pop('depends', None) or [])}]
        protocol_conf = conf.pop('protocol', None)
        service = cls(commands_modules=commands, router_mapping=router_mapping,
                      subscriber=subscriber, depends=depends, **conf)
        if svc_alias: service.alias = svc_alias
        service.config = conf
        if protocol_conf: service.add_dependency(_build_protocol(protocol_conf))
        return service

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()
