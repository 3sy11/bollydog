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
    routers: ClassVar[dict] = {}
    subscribers: ClassVar[dict] = {}
    depends: ClassVar[list] = []
    protocol = None

    def __init__(self, commands=None, routers=None,
                 subscribers=None, depends=None, **kwargs):
        super().__init__(**kwargs)
        self.commands = commands or []
        self.routers = routers or {}
        self.subscribers = subscribers or {}
        self.depends = depends or []

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    @classmethod
    def create_from(cls, **conf):
        svc_alias = conf.pop('alias', None)
        commands = [*{*(cls.commands or []), *(conf.pop('commands', None) or [])}]
        routers = {**(cls.routers or {}), **(conf.pop('routers', None) or {})}
        subscribers = {**(cls.subscribers or {}), **(conf.pop('subscribers', None) or {})}
        depends = [*{*(cls.depends or []), *(conf.pop('depends', None) or [])}]
        protocol_conf = conf.pop('protocol', None)
        service = cls(commands=commands, routers=routers,
                      subscribers=subscribers, depends=depends, **conf)
        if svc_alias: service.alias = svc_alias
        service.config = conf
        if protocol_conf: service.add_dependency(_build_protocol(protocol_conf))
        return service

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()
