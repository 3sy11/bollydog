import pathlib
import logging
import msgspec
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from bollydog.adapters._base import FileProtocol

logger = logging.getLogger(__name__)


class LocalFileProtocol(FileProtocol):

    def __init__(self, path: str | pathlib.Path, **kwargs) -> None:
        self.path = pathlib.Path(path) if isinstance(path, str) else path
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self.adapter = self.path

    async def read(self, path: str):
        file = self.path / path
        if not file.exists(): raise FileNotFoundError(file.as_posix())
        with open(file.as_posix(), 'r', encoding='utf-8') as f:
            return f.read()

    async def write(self, path: str, data):
        file = self.path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file.as_posix(), 'w', encoding='utf-8') as f:
            f.write(data if isinstance(data, str) else str(data))
        return True


class TOMLFileProtocol(FileProtocol):

    def __init__(self, path: str | pathlib.Path, **kwargs) -> None:
        self.path = pathlib.Path(path) if isinstance(path, str) else path
        self._data: dict = {}
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data = msgspec.toml.decode(self.path.read_bytes())
        self.adapter = True
        logger.debug(f"TOML on_start: {self.path.as_posix()}, loaded {len(self._data)} keys")

    async def read(self, path: str = None) -> dict:
        return self._data

    async def write(self, path: str = None, data: dict = None) -> bool:
        if data is not None:
            self._data = data
        self.path.write_bytes(msgspec.toml.encode(self._data))
        logger.debug(f"TOML write: {self.path.as_posix()}")
        return True

    def _resolve_key(self, key: str, create: bool = False) -> tuple[dict | None, str]:
        keys = key.split('.')
        current = self._data
        for k in keys[:-1]:
            if k not in current:
                if create:
                    current[k] = {}
                else:
                    return None, keys[-1]
            current = current[k]
            if not isinstance(current, dict):
                return None, keys[-1]
        return current, keys[-1]

    async def get(self, key: str, default: Any = None) -> Any:
        parent, final_key = self._resolve_key(key)
        result = default if parent is None else parent.get(final_key, default)
        logger.debug(f"TOML get: {key} = {result}")
        return result

    async def set(self, key: str, value: Any, flush: bool = True) -> bool:
        parent, final_key = self._resolve_key(key, create=True)
        parent[final_key] = value
        logger.debug(f"TOML set: {key} = {value}")
        return await self.write() if flush else True

    async def delete(self, key: str, flush: bool = True) -> bool:
        parent, final_key = self._resolve_key(key)
        if parent is None or final_key not in parent:
            return False
        del parent[final_key]
        logger.debug(f"TOML delete: {key}")
        return await self.write() if flush else True

    async def merge(self, updates: dict, deep: bool = True, flush: bool = True) -> bool:
        self._deep_merge(self._data, updates) if deep else self._data.update(updates)
        logger.debug(f"TOML merge: {list(updates.keys())}")
        return await self.write() if flush else True

    def _deep_merge(self, base: dict, updates: dict) -> None:
        for k, v in updates.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    async def keys(self, prefix: str = '') -> list[str]:
        data = self._data
        if prefix:
            parent, _ = self._resolve_key(prefix + '.x')
            if parent is None:
                return []
            data = parent
        result = []
        self._flatten_keys(data, prefix, result)
        return result

    def _flatten_keys(self, data: dict, prefix: str, result: list) -> None:
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            self._flatten_keys(v, full_key, result) if isinstance(v, dict) else result.append(full_key)
