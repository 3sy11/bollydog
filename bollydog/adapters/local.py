import pathlib
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from bollydog.models.protocol import Protocol


class LogProtocol(Protocol):

    def create(self):
        return True


class FileProtocol(Protocol):

    def __init__(self, path: str | pathlib.Path, **kwargs) -> None:
        self.path = pathlib.Path(path) if isinstance(path, str) else path
        super().__init__(**kwargs)

    def create(self):
        return True

    @asynccontextmanager
    async def connect(self, filename=None) -> AsyncGenerator:
        file = self.path / filename
        with open(file.as_posix(), 'a+', encoding='utf-8') as f:
            yield f

    async def write(self, filename, text):
        async with self.connect(filename) as f:
            f.write(text)
        return True

    async def read(self, filename):
        file = self.path / filename
        if not file.exists():
            raise FileNotFoundError(file.as_posix())
        async with self.connect(filename) as f:
            f.seek(0)
            text = f.read()
        return text


class NoneProtocol(Protocol):

    def create(self):
        return True


class MemoryProtocol(Protocol):

    def create(self):
        return {}

    async def get(self, key: str):
        return self.adapter.get(key)

    async def set(self, key: str, value, ttl: int = None):
        self.adapter[key] = value

    async def remove(self, key: str):
        self.adapter.pop(key, None)
