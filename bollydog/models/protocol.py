from typing import Any

from bollydog.models.base import BaseService


class Protocol(BaseService, abstract=True):
    domain = "adapters"
    adapter: Any = None
    protocol: 'Protocol' = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def create_from(cls, **conf):
        protocol = conf.pop('protocol', None)
        instance = super().create_from(**conf)
        instance._protocol = protocol
        return instance

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    async def __aenter__(self):
        await self.maybe_start()
        return self.adapter

    async def __aexit__(self, *exc_info):
        pass

    def __repr__(self):
        return f'<Protocol {self.__class__.__name__}>'
