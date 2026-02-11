import abc
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from bollydog.models.base import BaseService


class Protocol(BaseService, abstract=True):
    adapter: Any
    # queue: list[BaseEvent]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.adapter = self.create()
        assert self.adapter

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
