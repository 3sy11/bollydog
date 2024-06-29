import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from bollydog.models.protocol import UnitOfWork, Protocol


class LogUnitOfWork(UnitOfWork):

    async def context(self) -> AsyncGenerator:
        pass

    async def create_engine(self):
        pass

    async def new_session(self):
        pass

    async def close_session(self):
        pass


class LogProtocol(Protocol):
    def __init__(self, unit_of_work: UnitOfWork, **kwargs):
        super().__init__(unit_of_work, **kwargs)
        self.logger = logging.getLogger(__name__)

    async def log(self, message):
        self.logger.info(message.to_json())  # #
        return True


class FileUnitOfWork(UnitOfWork):

    async def context(self) -> AsyncGenerator:
        pass

    async def create_engine(self):
        pass

    async def new_session(self):
        pass

    async def close_session(self):
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
    async def context(self) -> AsyncGenerator:
        yield

    async def create_engine(self):
        pass

    async def new_session(self):
        pass

    async def close_session(self):
        pass


class NoneProtocol(Protocol):
    def __init__(self, unit_of_work: UnitOfWork, **kwargs):
        super().__init__(unit_of_work, **kwargs)
