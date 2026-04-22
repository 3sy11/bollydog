import abc
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from bollydog.models.service import BaseService


class Protocol(BaseService, abstract=True):
    adapter: Any
    protocol: 'Protocol' = None

    def __init__(self, protocol=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol = protocol
        if protocol is not None:
            self.add_dependency(protocol)
        self.adapter = self.create()
        assert self.adapter is not None

    @abc.abstractmethod
    def create(self) -> Any:
        """创建底层适配器/连接，子类必须实现"""
        ...

    def delete(self):
        ...

    async def on_stop(self) -> None:
        self.delete()
        await super().on_stop()

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        yield self.adapter

    def __repr__(self):
        return f'<Protocol {self.__class__.__name__}>'
