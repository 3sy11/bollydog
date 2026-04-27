from typing import Any
from bollydog.models.service import BaseService


class Protocol(BaseService, abstract=True):
    adapter: Any = None
    protocol: 'Protocol' = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        if isinstance(service, Protocol) and self.protocol is None:
            self.protocol = service
        return super().add_dependency(service)

    async def __aenter__(self):
        return self.adapter

    async def __aexit__(self, *exc_info):
        pass

    def __repr__(self):
        return f'<Protocol {self.__class__.__name__}>'
