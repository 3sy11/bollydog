import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from bollydog.models.protocol import UnitOfWork, Protocol


class LogUnitOfWork(UnitOfWork):

    async def create(self):
        ...


class LogProtocol(Protocol):
    ...


class FileUnitOfWork(UnitOfWork):

    def __init__(self, path):
        self.path = path
        super().__init__()

    async def create(self):
        return open(self.path, 'w+')


class FileProtocol(Protocol):
    ...


class NoneUnitOfWork(UnitOfWork):

    async def create(self):
        ...


class NoneProtocol(Protocol):
    ...
