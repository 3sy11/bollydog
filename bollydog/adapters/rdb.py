import time
import sqlmodel
import uuid
import importlib
from sqlalchemy.schema import CreateTable
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type, List

from sqlalchemy import select, insert, delete, update, MetaData, text, inspect, orm, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from bollydog.models.protocol import UnitOfWork, Protocol
from bollydog.models.base import BaseDomain
from bollydog.utils.base import get_hostname

duckdb = importlib.import_module('duckdb', package=None)

# bollydog.models.base._ModelMixin
class SQLModelDomain(sqlmodel.SQLModel, BaseDomain):
    __abstract__ = True
    id: int = sqlmodel.Field(primary_key=True)
    iid: str = sqlmodel.Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    created_time: float = sqlmodel.Field(default_factory=lambda: int(time.time() * 1000), index=True)
    update_time: float = sqlmodel.Field(default_factory=lambda: int(time.time() * 1000), index=True)
    sign: int = sqlmodel.Field(default=0)
    created_by: str = sqlmodel.Field(default=get_hostname(), max_length=50)

    __table_args__ = (
        UniqueConstraint("iid"),
    )

class SqlAlchemyAsyncUnitOfWork(UnitOfWork):
    async_session = None

    def __init__(self,
                 url: str,
                 metadata: MetaData,
                 *args, **kwargs):
        self.metadata = metadata
        self.url = url
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f'<SqlAlchemyAsyncUnitOfWork {self.url}>'

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncSession, None]:
        try:
            async with self.async_session.begin() as session:
                yield session
        except BaseException as e:
            self.logger.exception(e)
            raise e

    def create(self) -> AsyncEngine:
        self.adapter = create_async_engine(
            self.url,
            echo=False,
            echo_pool=False,
            hide_parameters=not False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.async_session = async_sessionmaker(self.adapter, expire_on_commit=True)
        return self.adapter

    async def create_all(self, metadata=None):
        async with self.adapter.begin() as conn:
            if metadata:
                await conn.run_sync(metadata.create_all)
            else:
                await conn.run_sync(self.metadata.create_all)


class SqlAlchemyProtocol(Protocol):

    async def add(self, item: SQLModelDomain, *args, **kwargs):
        cls = inspect(item).mapper.local_table
        async with self.unit_of_work.connect() as session:
            stmt = insert(cls).values(**item.model_dump())
            stmt = stmt.returning(cls.c.id)
            res = await session.execute(stmt)
            await session.commit()
            res = res.scalars().first()
            item.id = res
        return item

    async def add_all(self, items: List[SQLModelDomain], *args, **kwargs):
        if not items:
            return items
        table = inspect(items[0]).mapper.local_table  # <
        async with self.unit_of_work.connect() as session:
            stmt = insert(table).values([item.model_dump() for item in items])
            stmt = stmt.returning(table.c.id)
            res = await session.execute(stmt)
            res = res.fetchall()
            await session.commit()
        for i, r in zip(items, res):
            i.id = r.id
        return items

    async def get(self, cls: Type[SQLModelDomain], *args, **kwargs):
        stmt = select(cls)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
            res = result.scalars().first()
            res = res.model_dump()
        return res

    async def list(self, cls: Type[SQLModelDomain], *args, **kwargs):
        stmt = select(cls)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def update(self, cls: Type[SQLModelDomain], item_id, *args, **kwargs):
        stmt = update(cls).where(cls.id == item_id)
        stmt = stmt.values(update_time=time.time() * 1000, **kwargs)
        stmt = stmt.returning(cls)
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def delete(self, cls: Type[SQLModelDomain], item_id, *args, **kwargs):
        stmt = delete(cls).where(cls.id == item_id)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        stmt = stmt.returning(cls)
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def search(self, *args, **kwargs):
        query = text(kwargs['query'])
        async with self.unit_of_work.connect() as session:
            result = await session.execute(query)
        return result.fetchall()


# < try to use SqlAlchemyProtocol
class DuckDBUnitOfWork(UnitOfWork):
    def __init__(self, url, metadata: MetaData = None, *args, **kwargs):
        self.url = url or ':default:'
        self.metadata = metadata
        self.connection = None
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f'<DuckDBAsyncUnitOfWork {self.url}>'

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[duckdb.DuckDBPyConnection, None]:
        if not self.connection:
            self.connection = duckdb.connect(self.url)
        # < load_extension
        yield self.connection
        self.connection.close()
        self.connection = None

    def create(self, url=None):
        # check connection is closed, because duckdb feature, using self.connection to execute create tables;
        url = url or self.url
        self.connection = duckdb.connect(url)
        self.connection.commit()
        self.connection.close()
        self.connection = None
        return url

    def create_all(self, metadata=None):
        metadata = metadata or self.metadata
        for table in metadata.sorted_tables:
            create_stmt = str(CreateTable(table).compile())
            self.connection.execute(create_stmt)
            self.connection.execute(f"CREATE SEQUENCE {table.name}idseq START 1;")  # # add autoincrement id
            self.connection.execute(
                f"ALTER TABLE {table.name} ALTER COLUMN id SET DEFAULT NEXTVAL('{table.name}idseq');")
