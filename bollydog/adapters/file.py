import pathlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from bollydog.adapters._base import FileProtocol


class LocalFileProtocol(FileProtocol):

    def __init__(self, path: str | pathlib.Path, **kwargs) -> None:
        self.path = pathlib.Path(path) if isinstance(path, str) else path
        super().__init__(**kwargs)

    def create(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return True

    @asynccontextmanager
    async def connect(self, filename=None) -> AsyncGenerator:
        file = self.path / filename
        with open(file.as_posix(), 'a+', encoding='utf-8') as f:
            yield f

    async def read(self, path: str):
        file = self.path / path
        if not file.exists():
            raise FileNotFoundError(file.as_posix())
        async with self.connect(path) as f:
            f.seek(0)
            return f.read()

    async def write(self, path: str, data):
        file = self.path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file.as_posix(), 'w', encoding='utf-8') as f:
            f.write(data if isinstance(data, str) else str(data))
        return True
