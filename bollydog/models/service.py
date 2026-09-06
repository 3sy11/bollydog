import logging
from typing import ClassVar, List

from bollydog.models.base import BaseCommand, BaseService
from bollydog.models.protocol import Protocol

logger = logging.getLogger(__name__)

__all__ = ['BaseService', 'AppService']


class AppService(BaseService, abstract=True):
    commands: ClassVar[List[str]] = []
    routers: ClassVar[dict] = {}
    subscribers: ClassVar[dict] = {}
    protocol = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.commands = []
        self.routers = {}
        self.subscribers = {}
        self.depends = {}

    @classmethod
    def create_from(cls, **conf):
        commands = [*{*(cls.commands or []), *(conf.pop('commands', None) or [])}]
        routers = {**(cls.routers or {}), **(conf.pop('routers', None) or {})}
        subscribers = {**(cls.subscribers or {}), **(conf.pop('subscribers', None) or {})}
        protocol = conf.pop('protocol', None)
        depends = conf.pop('depends', None) or []

        service = super().create_from(**conf)
        service.commands = commands
        service.routers = routers
        service.subscribers = subscribers
        service._protocol = protocol
        service._depends = depends
        return service

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()
