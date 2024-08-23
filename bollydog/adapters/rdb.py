import time
import sqlmodel
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type, List

from sqlalchemy import select, insert, delete, update, MetaData, text, inspect, orm
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from bollydog.config import IS_DEBUG
from bollydog.models.protocol import UnitOfWork, Protocol
from bollydog.models.base import BaseDomain
from bollydog.utils.base import get_hostname


# bollydog.models.base._ModelMixin
class SQLModelDomain(sqlmodel.SQLModel, BaseDomain):
    __abstract__ = True
    id: int = sqlmodel.Field(default=None, primary_key=True)
    iid: str = sqlmodel.Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    created_time: float = sqlmodel.Field(default_factory=lambda: int(time.time() * 1000), index=True)
    update_time: float = sqlmodel.Field(default_factory=lambda: int(time.time() * 1000))
    sign: int = sqlmodel.Field(default=0)
    created_by: str = sqlmodel.Field(default=get_hostname(), max_length=50)


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
        adapter = create_async_engine(
            self.url,
            echo=IS_DEBUG,
            echo_pool=IS_DEBUG,
            hide_parameters=not IS_DEBUG,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.async_session = async_sessionmaker(adapter, expire_on_commit=True)
        return adapter

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
