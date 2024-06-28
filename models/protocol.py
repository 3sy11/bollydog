import abc
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

from pydantic import AnyUrl

from models.base import BaseService, BaseMessage


class UnitOfWork(BaseService, abstract=True):

    def __init__(self, url: AnyUrl, *args, **kwargs):
        super().__init__()
        self.url = url

    async def on_start(self) -> None:
        await super().on_start()
        await self.new_session()

    async def on_stop(self) -> None:
        await self.close_session()
        await super().on_stop()

    @abc.abstractmethod
    @asynccontextmanager
    async def context(self) -> AsyncGenerator:
        ...

    @abc.abstractmethod
    async def new_session(self):
        ...

    async def close_session(self):
        ...


class Protocol(abc.ABC):
    events: List[BaseMessage]
    unit_of_work: UnitOfWork

    def __init__(self, unit_of_work: UnitOfWork, *args, **kwargs):
        super().__init__()
        self.events = []
        self.unit_of_work = unit_of_work
