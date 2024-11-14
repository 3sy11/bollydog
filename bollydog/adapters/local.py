import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from bollydog.models.protocol import UnitOfWork, Protocol


class LogUnitOfWork(UnitOfWork):

    def create(self):
        return True


class LogProtocol(Protocol):
    ...


class FileUnitOfWork(UnitOfWork):

    def __init__(self, path):
        self.path = path
        super().__init__()

    def create(self):
        return open(self.path, 'w+')


class FileProtocol(Protocol):
    ...


class NoneUnitOfWork(UnitOfWork):

    def create(self):
        return True


class NoneProtocol(Protocol):
    ...
