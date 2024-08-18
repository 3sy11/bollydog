import time
import databases
import sqlalchemy
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type, Dict, List
from pydantic_core import PydanticUndefined
from annotated_types import MaxLen
from sqlalchemy import select, delete, update, MetaData, Column, Integer, String, Float, Table, text, Text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.orm import registry
from bollydog.config import IS_DEBUG
from bollydog.models.protocol import UnitOfWork, Protocol
from bollydog.models.base import BaseDomain

annotation_mapping: Dict[Type, Type] = {
    str: String,
    float: Float,
    int: Integer,
    dict: Text,
}
DEFAULT_STR_LEN = 50
sqlalchemy_class_mapping: Dict[Type[BaseDomain], Type] = {}
# r=registry()


def map_imperatively(cls: Type[BaseDomain], registry):
    """
    pydantic model to sqlalchemy model, bind to pydantic model `Config.orm_mapper_registry_class` attribute
    # < use `ormar` instead
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
    sqlalchemy_class_mapping[cls] = orm_cls


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
        self.async_session = async_sessionmaker(adapter, expire_on_commit=False)
        return adapter

    async def create_all(self, metadata=None):
        async with self.adapter.begin() as conn:
            if metadata:
                await conn.run_sync(metadata.create_all)
            else:
                await conn.run_sync(self.metadata.create_all)


class SqlAlchemyProtocol(Protocol):

    async def _add(self, item, *args, **kwargs):
        async with self.unit_of_work.connect() as session:
            # table = inspect(item).mapper.local_table
            # stmt = table.insert()
            # query = str(stmt.compile())
            # text(query)
            # await session.execute(stmt, values=values)
            session.add(item)
            await session.commit()
        return item

    async def _add_all(self, items, *args, **kwargs):
        async with self.unit_of_work.connect() as session:
            session.add_all(items)
            await session.commit()
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
        _item = sqlalchemy_class_mapping[item.__class__](**item.model_dump())
        _item = await self._add(_item, *args, **kwargs)
        return _item.__dict__

    async def add_all(self, items: List[BaseDomain], *args, **kwargs):
        _is = [sqlalchemy_class_mapping[i.__class__](**i.model_dump()) for i in items]
        return await self._add_all(_is, *args, **kwargs)

    async def get(self, cls: Type[BaseDomain], *args, **kwargs):
        return await self._get(sqlalchemy_class_mapping[cls], *args, **kwargs)

    async def delete(self, cls: Type[BaseDomain], item_id, *args, **kwargs):
        return await self._delete(sqlalchemy_class_mapping[cls], item_id, *args, **kwargs)

    async def list(self, cls: Type[BaseDomain], *args, **kwargs):
        return await self._list(sqlalchemy_class_mapping[cls], *args, **kwargs)

    async def update(self, cls: Type[BaseDomain], item_id, *args, **kwargs):
        return await self._update(sqlalchemy_class_mapping[cls], item_id, *args, **kwargs)

    async def search(self, *args, **kwargs):
        return await self._search(*args, **kwargs)


class DatabasesUnitOfWork(UnitOfWork):

    def __init__(self, url, metadata,dialect=None):
        self.url = url
        self.metadata = metadata
        self.dialect = dialect
        super().__init__()

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator:
        async with self.adapter.connection() as connect:
            yield connect

    def create(self):
        adapter = databases.Database(self.url)
        self.dialect = getattr(sqlalchemy.dialects,adapter.url.dialect).dialect()
        return adapter

    async def create_all(self, metadata=None):
        metadata = metadata or self.metadata
        async with self.connect() as conn:
            for table in metadata.tables.values():
                schema = sqlalchemy.schema.CreateTable(table, if_not_exists=True)
                query = str(schema.compile(dialect=self.dialect))
                await conn.execute(query=query)
