import time
import uuid
import asyncio
import sqlmodel
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Type, List

from sqlalchemy import select, insert, delete, update, MetaData, text, inspect, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.schema import CreateTable
from bollydog.adapters._base import CRUDProtocol, TransactionMixin, StreamMixin, DialectMixin
from bollydog.models.base import BaseDomain


class SQLModelDomain(sqlmodel.SQLModel, BaseDomain):
    __abstract__ = True
    id: int = sqlmodel.Field(primary_key=True)
    iid: str = sqlmodel.Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    created_time: float = sqlmodel.Field(default_factory=lambda: int(time.time() * 1000), index=True)
    update_time: float = sqlmodel.Field(default_factory=lambda: int(time.time() * 1000), index=True)
    sign: int = sqlmodel.Field(default=1)
    created_by: str = sqlmodel.Field(default='', max_length=50, index=True)
    __table_args__ = (UniqueConstraint("iid"),)


# ─── SqlAlchemyProtocol ───────────────────────────────────────

class SqlAlchemyProtocol(CRUDProtocol, DialectMixin, TransactionMixin, StreamMixin):
    """Universal SQL CRUD via SQLAlchemy dialect system.

    Supported URLs (async drivers):
      postgresql+asyncpg://   mysql+aiomysql://   sqlite+aiosqlite://
      oracle+oracledb://      mssql+aioodbc://

    DialectMixin provides compile(stmt) for SQL generation / logging.
    """
    async_session = None

    def __init__(self, url: str, metadata: MetaData = None, *args, **kwargs):
        self.metadata = metadata
        self.url = url
        super().__init__(*args, **kwargs)
        self._dialect = self.adapter.dialect

    def __repr__(self):
        return f'<SqlAlchemyProtocol {self.url}>'

    @property
    def dialect_name(self) -> str:
        return self.adapter.dialect.name

    def create(self) -> AsyncEngine:
        self.adapter = create_async_engine(self.url, echo=False, echo_pool=False, hide_parameters=True, pool_pre_ping=True, pool_recycle=3600)
        self.async_session = async_sessionmaker(self.adapter, expire_on_commit=True)
        return self.adapter

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncSession, None]:
        try:
            async with self.async_session.begin() as session:
                yield session
        except BaseException as e:
            self.logger.exception(e)
            raise e

    async def create_all(self, metadata=None):
        async with self.adapter.begin() as conn:
            await conn.run_sync((metadata or self.metadata).create_all)

    async def execute_raw(self, sql: str, **params):
        """Execute raw SQL text — dialect-specific features (pgvector, DuckDB funcs, etc.)."""
        async with self.connect() as session:
            result = await session.execute(text(sql), params or None)
        return result.fetchall()

    async def add(self, item, **ctx):
        cls = inspect(item).mapper.local_table
        async with self.connect() as session:
            stmt = insert(cls).values(**item.model_dump()).returning(cls.c.id)
            res = await session.execute(stmt)
            await session.commit()
            item.id = res.scalars().first()
        return item

    async def add_all(self, items: list, **ctx):
        if not items:
            return items
        table = inspect(items[0]).mapper.local_table
        async with self.connect() as session:
            stmt = insert(table).values([item.model_dump() for item in items]).returning(table.c.id)
            res = await session.execute(stmt)
            res = res.fetchall()
            await session.commit()
        for i, r in zip(items, res):
            i.id = r.id
        return items

    async def get(self, **query):
        cls = query.pop('cls')
        stmt = select(cls)
        for column, value in query.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.connect() as session:
            result = await session.execute(stmt)
            res = result.scalars().first()
            return res.model_dump() if res else None

    async def list(self, **query) -> list:
        cls = query.pop('cls')
        stmt = select(cls)
        for column, value in query.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def update(self, query: dict, data: dict):
        cls = query.pop('cls')
        item_id = query.pop('id')
        data.setdefault('update_time', time.time() * 1000)
        stmt = update(cls).where(cls.id == item_id).values(**data).returning(cls)
        async with self.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def delete(self, **query):
        cls = query.pop('cls')
        item_id = query.pop('id')
        stmt = delete(cls).where(cls.id == item_id)
        for column, value in query.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        stmt = stmt.returning(cls)
        async with self.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def search(self, *args, **kwargs):
        return await self.execute_raw(kwargs['query'])

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session.begin() as session:
            yield session

    async def stream(self, **query) -> AsyncIterator:
        cls = query.pop('cls')
        stmt = select(cls)
        for column, value in query.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.async_session() as session:
            result = await session.stream_scalars(stmt)
            async for row in result:
                yield row


# ─── PostgreSQLProtocol ───────────────────────────────────────

class PostgreSQLProtocol(SqlAlchemyProtocol):
    """PostgreSQL dialect. URL: postgresql+asyncpg://user:pass@host/db

    Adds: ON CONFLICT upsert, pgvector similarity search.
    """

    async def upsert(self, item, conflict_columns: list = None, **ctx):
        """INSERT ... ON CONFLICT DO UPDATE / DO NOTHING."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        table = inspect(item).mapper.local_table
        data = item.model_dump()
        stmt = pg_insert(table).values(**data)
        if conflict_columns:
            update_cols = {c: stmt.excluded[c] for c in data if c not in conflict_columns}
            stmt = stmt.on_conflict_do_update(index_elements=conflict_columns, set_=update_cols)
        else:
            stmt = stmt.on_conflict_do_nothing()
        stmt = stmt.returning(table.c.id)
        async with self.connect() as session:
            res = await session.execute(stmt)
            await session.commit()
            item.id = res.scalars().first()
        return item

    async def similarity(self, cls, vector_key: str, embedding: list[float], top_k=10, **kwargs):
        """pgvector cosine distance: ORDER BY embedding <=> query LIMIT k."""
        dist = text(f"{vector_key} <=> '{embedding}' AS distance")
        stmt = select(cls, dist).order_by(text('distance')).limit(top_k)
        if 'where' in kwargs:
            stmt = stmt.where(kwargs['where'])
        async with self.connect() as session:
            return (await session.execute(stmt)).fetchall()


# ─── MySQLProtocol ────────────────────────────────────────────

class MySQLProtocol(SqlAlchemyProtocol):
    """MySQL/MariaDB dialect. URL: mysql+aiomysql://user:pass@host/db

    Adds: ON DUPLICATE KEY UPDATE upsert, INSERT IGNORE, utf8mb4 charset.
    """

    def create(self) -> AsyncEngine:
        self.adapter = create_async_engine(self.url, echo=False, pool_pre_ping=True, pool_recycle=3600, connect_args={"charset": "utf8mb4"})
        self.async_session = async_sessionmaker(self.adapter, expire_on_commit=True)
        return self.adapter

    async def upsert(self, item, unique_keys: list = None, **ctx):
        """INSERT ... ON DUPLICATE KEY UPDATE."""
        from sqlalchemy.dialects.mysql import insert as mysql_insert
        table = inspect(item).mapper.local_table
        data = item.model_dump()
        stmt = mysql_insert(table).values(**data)
        update_cols = {k: v for k, v in data.items() if k not in (unique_keys or [])}
        stmt = stmt.on_duplicate_key_update(**update_cols)
        async with self.connect() as session:
            await session.execute(stmt)
            await session.commit()
        return item

    async def insert_ignore(self, item, **ctx):
        """INSERT IGNORE — skip on duplicate key."""
        from sqlalchemy.dialects.mysql import insert as mysql_insert
        table = inspect(item).mapper.local_table
        stmt = mysql_insert(table).values(**item.model_dump()).prefix_with('IGNORE')
        async with self.connect() as session:
            await session.execute(stmt)
            await session.commit()
        return item


# ─── DuckDBProtocol ───────────────────────────────────────────

class DuckDBProtocol(CRUDProtocol, DialectMixin):
    """DuckDB native engine + DialectMixin stmt compilation.

    Uses duckdb.connect() for max performance (DataFrame, Parquet, vector search).
    DialectMixin.compile(stmt) generates DuckDB-dialect SQL from SQLAlchemy stmts.
    """

    def __init__(self, url, metadata: MetaData = None, *args, **kwargs):
        self.url = url or ':memory:'
        self.metadata = metadata
        super().__init__(*args, **kwargs)
        try:
            self._dialect = self._resolve_dialect('duckdb')
        except Exception:
            self._dialect = None
            self.logger.warning('duckdb dialect not available, compile() disabled (pip install duckdb-engine)')

    def __repr__(self):
        return f'<DuckDBProtocol {self.url}>'

    def create(self):
        import duckdb
        return duckdb.connect(self.url)

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        yield self.adapter

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def create_all(self, metadata=None):
        metadata = metadata or self.metadata
        if not metadata:
            return
        tables = self.adapter.execute('SHOW TABLES').fetchall()
        for table in metadata.sorted_tables:
            if (table.name,) in tables:
                self.logger.warning(f'Table {table.name} already exists, skipping...')
                continue
            create_stmt = str(CreateTable(table).compile())
            self.adapter.execute(create_stmt)
            self.adapter.execute(f"CREATE OR REPLACE SEQUENCE {table.name}idseq START 1;")
            self.adapter.execute(f"ALTER TABLE {table.name} ALTER COLUMN id SET DEFAULT NEXTVAL('{table.name}idseq');")

    async def execute_raw(self, sql: str, **params):
        """Execute raw SQL — DuckDB native (vector search, DataFrame, Parquet)."""
        return await self._run(self.adapter.execute, sql)

    async def add(self, item, **ctx):
        table = ctx.get('table', 'default')
        return await self._run(self.adapter.execute, f"INSERT INTO {table} VALUES (?)", [item])

    async def add_all(self, items: list, **ctx):
        table = ctx.get('table', 'default')
        return await self._run(self.adapter.executemany, f"INSERT INTO {table} VALUES (?)", [[i] for i in items])

    async def get(self, **query):
        sql = query.get('query', '')
        return await self._run(lambda: self.adapter.execute(sql).fetchone())

    async def list(self, **query) -> list:
        sql = query.get('query', '')
        return await self._run(lambda: self.adapter.execute(sql).fetchall())

    async def update(self, query: dict, data: dict):
        sql = query.get('query', '')
        return await self._run(lambda: self.adapter.execute(sql).fetchall())

    async def delete(self, **query):
        sql = query.get('query', '')
        return await self._run(lambda: self.adapter.execute(sql).fetchall())

    async def on_stop(self) -> None:
        if self.adapter:
            self.adapter.close()
        await super().on_stop()
