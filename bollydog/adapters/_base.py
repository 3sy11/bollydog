import abc
from contextlib import asynccontextmanager
from typing import AsyncIterator, AsyncGenerator
from bollydog.models.protocol import Protocol


# ─── ABC ───────────────────────────────────────────────────────

class KVProtocol(Protocol, abstract=True):
    """Key-Value storage: Session, cache, simple state."""
    @abc.abstractmethod
    async def get(self, key: str): ...
    @abc.abstractmethod
    async def set(self, key: str, value, ttl: int = None): ...
    @abc.abstractmethod
    async def remove(self, key: str): ...
    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None
    async def keys(self, pattern: str = '*') -> list:
        raise NotImplementedError


class CRUDProtocol(Protocol, abstract=True):
    """Structured data CRUD: SQL, Elasticsearch, DuckDB table queries."""
    @abc.abstractmethod
    async def add(self, item, **ctx): ...
    @abc.abstractmethod
    async def add_all(self, items: list, **ctx): ...
    @abc.abstractmethod
    async def get(self, **query): ...
    @abc.abstractmethod
    async def list(self, **query) -> list: ...
    @abc.abstractmethod
    async def update(self, query: dict, data: dict): ...
    @abc.abstractmethod
    async def delete(self, **query): ...
    async def count(self, **query) -> int:
        return len(await self.list(**query))


class GraphProtocol(Protocol, abstract=True):
    """Graph database: Neo4j, GraphScope."""
    @abc.abstractmethod
    async def execute(self, query: str, **params): ...


class FileProtocol(Protocol, abstract=True):
    """File I/O."""
    @abc.abstractmethod
    async def read(self, path: str): ...
    @abc.abstractmethod
    async def write(self, path: str, data): ...


# ─── Mixin ─────────────────────────────────────────────────────

class BatchMixin:
    """Bulk update/delete for CRUDProtocol implementations."""
    async def update_all(self, items: list, **ctx) -> list:
        return [await self.update(item, **ctx) for item in items]
    async def delete_all(self, items: list, **ctx) -> list:
        return [await self.delete(item, **ctx) for item in items]


class StreamMixin:
    """Cursor-based streaming for large result sets."""
    async def stream(self, **query) -> AsyncIterator:
        raise NotImplementedError


class TransactionMixin:
    """Atomic operation context."""
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        raise NotImplementedError
        yield  # noqa: make it a generator


class DialectMixin:
    """SQLAlchemy stmt → SQL pure compilation. No engine required.

    Mix into any Protocol to get compile(stmt) ability.
    Set _dialect via engine.dialect (SqlAlchemyProtocol) or _resolve_dialect(name) (native drivers).
    """
    _dialect = None

    def _resolve_dialect(self, dialect_name: str):
        from sqlalchemy.dialects import registry
        return registry.load(dialect_name)()

    def compile(self, stmt, literal_binds=False) -> tuple[str, dict]:
        kw = {"literal_binds": literal_binds} if literal_binds else {}
        compiled = stmt.compile(dialect=self._dialect, compile_kwargs=kw)
        return str(compiled), dict(compiled.params) if not literal_binds else {}
