import pathlib
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

    def __init__(self, path: str | pathlib.Path, **kwargs) -> None:
        if isinstance(path, str):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        super().__init__(**kwargs)

    def create(self):
        return True

    @asynccontextmanager
    async def connect(self, filename) -> AsyncGenerator:
        file = self.path / filename
        with open(file.as_posix(), 'a+',encoding='utf-8') as f:
            yield f


class FileProtocol(Protocol):

    async def write(self, filename, text):
        async with self.unit_of_work.connect(filename) as f:
            f.write(text)
        return True

    async def read(self, filename):
        file = self.unit_of_work.path / filename
        if not file.exists():
            raise FileNotFoundError(file.as_posix())
        async with self.unit_of_work.connect(filename) as f:
            f.seek(0)
            text = f.read()
        return text


class NoneUnitOfWork(UnitOfWork):

    def create(self):
        return True


class NoneProtocol(Protocol):
    ...
