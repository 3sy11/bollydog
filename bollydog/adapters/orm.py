import abc
import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type, Dict, TypeVar, List

from annotated_types import MaxLen
from bollydog.config import IS_DEBUG
from bollydog.models.protocol import UnitOfWork, Protocol
from pydantic_core import PydanticUndefined
from sqlalchemy import select, delete, update, MetaData, Column, Integer, String, JSON, Float, Table, text, Text
from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, async_sessionmaker, AsyncSession

from bollydog.globals import message
from bollydog.models.base import BaseDomain

annotation_mapping: Dict[Type, Type] = {
    str: String,
    float: Float,
    int: Integer,
    dict: Text,
}
DEFAULT_STR_LEN = 50
orm_class_mapping: Dict[Type[BaseDomain], Type] = {}


def map_imperatively(cls: Type[BaseDomain], registry):
    """
    pydantic model to sqlalchemy model, bind to pydantic model `Config.orm_mapper_registry_class` attribute
    """
    columns = [
        Column('id', Integer, primary_key=True, autoincrement=True),
        # Column('iid', String(50), index=True, unique=True),  # # special adapt
        Column('created_time', Float, index=True),
    ]
    for __name_pos, field in cls.model_fields.items():
        if __name_pos in ('created_time',):
            continue
        __type_pos = annotation_mapping[field.annotation]
        __kwargs = {}
        if field.default is None:
            __kwargs['nullable'] = True
        elif field.default is PydanticUndefined:
            pass
        else:
            __kwargs['default'] = field.default  # ?
        if __type_pos is String:
            for m in field.metadata:
                if isinstance(m, MaxLen):
                    __type_pos_arg = m.max_length
                    __type_pos = String(__type_pos_arg)
                    break
            else:
                __type_pos = String(DEFAULT_STR_LEN)
        columns.append(
            Column(__name_pos, __type_pos, **__kwargs)
        )

    orm_cls = type(cls.__name__, (object,), {})
    registry.map_imperatively(
        orm_cls,  # # noqa
        Table(cls.__name__.lower(), registry.metadata, *columns, )
    )
    orm_class_mapping[cls] = orm_cls


class SqlAlchemyAsyncUnitOfWork(UnitOfWork):
    async_session = None

    def __init__(self,
                 url: str,
                 metadata: MetaData,
                 *args, **kwargs):
        super().__init__(url=url, *args, **kwargs)
        self.metadata = metadata

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncSession, None]:
        try:
            async with self.async_session.begin() as session:
                yield session
        except BaseException as e:
            self.logger.exception(e)
            raise e

    def create(self):
        self.unit_of_work = create_async_engine(
            self.url,
            echo=IS_DEBUG,
            echo_pool=IS_DEBUG,
            hide_parameters=not IS_DEBUG,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.async_session = async_sessionmaker(self.unit_of_work, expire_on_commit=True)

    async def create_all(self, metadata=None):
        async with self.unit_of_work.begin() as conn:
            if metadata:
                await conn.run_sync(metadata.create_all)
            else:
                await conn.run_sync(self.metadata.create_all)


class SqlAlchemyProtocol(Protocol):
    unit_of_work: SqlAlchemyAsyncUnitOfWork

    async def _add(self, item, *args, **kwargs):
        async with self.unit_of_work.connect() as session:
            session.add(item)
        return item

    async def _add_all(self, items, *args, **kwargs):
        async with self.unit_of_work.connect() as session:
            session.add_all(items)
        return items

    async def _get(self, cls, *args, **kwargs):
        stmt = select(cls)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().first()

    async def _list(self, cls, *args, **kwargs):
        stmt = select(cls)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def _update(self, cls: Table, item_id, *args, **kwargs):
        stmt = update(cls).where(cls.id.is_(item_id))
        stmt = stmt.values(update_time=time.time() * 1000, **kwargs)
        stmt = stmt.returning(cls)
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def _delete(self, cls: Table, item_id, *args, **kwargs):
        stmt = delete(cls).where(cls.id.is_(item_id))
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        stmt = stmt.returning(cls)
        async with self.unit_of_work.connect() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def _search(self, *args, **kwargs):
        query = text(kwargs['query'])
        async with self.unit_of_work.connect() as session:
            result = await session.execute(query)
        return result.fetchall()

    async def add(self, item: BaseDomain, *args, **kwargs):
        _item = orm_class_mapping[item.__class__](**item.model_dump())
        _item = await self._add(_item, *args, **kwargs)
        return _item.__dict__

    async def add_all(self, items: List[BaseDomain], *args, **kwargs):
        _is = [orm_class_mapping[i.__class__](**i.model_dump()) for i in items]
        return await self._add_all(_is, *args, **kwargs)

    async def get(self, cls: Type[BaseDomain], *args, **kwargs):
        return await self._get(orm_class_mapping[cls], *args, **kwargs)

    async def delete(self, cls: Type[BaseDomain], item_id, *args, **kwargs):
        return await self._delete(orm_class_mapping[cls], item_id, *args, **kwargs)

    async def list(self, cls: Type[BaseDomain], *args, **kwargs):
        return await self._list(orm_class_mapping[cls], *args, **kwargs)

    async def update(self, cls: Type[BaseDomain], item_id, *args, **kwargs):
        return await self._update(orm_class_mapping[cls], item_id, *args, **kwargs)

    async def search(self, *args, **kwargs):
        return await self._search(*args, **kwargs)
