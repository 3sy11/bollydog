import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from bollydog.models.protocol import UnitOfWork, Protocol


class LogUnitOfWork(UnitOfWork):

    async def connect(self) -> AsyncGenerator:
        pass

    async def create_engine(self):
        pass

    async def create(self):
        pass

    async def delete(self):
        pass


class LogProtocol(Protocol):
    def __init__(self, unit_of_work: UnitOfWork, **kwargs):
        super().__init__(unit_of_work, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def log(self, message):
        self.logger.info(message.to_json())  # #
        return True


class FileUnitOfWork(UnitOfWork):

    async def connect(self) -> AsyncGenerator:
        pass

    async def create_engine(self):
        pass

    async def create(self):
        pass

    async def delete(self):
        pass


class FileProtocol(Protocol):
    def __init__(self, unit_of_work: UnitOfWork, **kwargs):
        super().__init__(unit_of_work, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def write(self, message):
        self.logger.info(message.to_json())
        return True


class NoneUnitOfWork(UnitOfWork):
    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        yield

    async def create_engine(self):
        pass

    async def create(self):
        pass

    async def delete(self):
        pass


class NoneProtocol(Protocol):
    def __init__(self, unit_of_work: UnitOfWork, **kwargs):
        super().__init__(unit_of_work, **kwargs)
