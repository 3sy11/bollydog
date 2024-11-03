import abc
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Any

from bollydog.models.base import BaseService, BaseMessage


class UnitOfWork(BaseService, abstract=True):
    adapter: Any

    def __init__(self, *args, **kwargs):
        super().__init__()

    def __repr__(self):
        return f'<UnitOfWork {self.__class__.__name__}>'

    async def on_start(self) -> None:
        if not self.adapter:
            self.adapter = self.create()

    async def on_stop(self) -> None:
        self.delete()
        await super().on_stop()

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        yield self.adapter

    @abc.abstractmethod
    def create(self) -> Any:
        # implementation depends on the adapter
        # assert self.adapter
        ...

    def delete(self):
        ...


class Protocol(abc.ABC):
    events: List[BaseMessage]
    unit_of_work: UnitOfWork

    def __init__(self, unit_of_work: UnitOfWork, *args, **kwargs):
        super().__init__()
        self.events = []
        self.unit_of_work = unit_of_work
        self.unit_of_work.create()

    def __repr__(self):
        return f'<Protocol {self.__class__.__name__}>: {self.unit_of_work.__repr__()}'

    def __str__(self):
        return self.__repr__()

    @property
    def adapter(self):
        return self.unit_of_work.adapter
