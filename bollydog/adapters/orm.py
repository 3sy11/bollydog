import abc
import asyncio
import time
import databases
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Type, Dict, TypeVar, List

from annotated_types import MaxLen
from bollydog.config import IS_DEBUG
from bollydog.models.protocol import UnitOfWork, Protocol
from pydantic import AnyUrl
from pydantic_core import PydanticUndefined
from sqlalchemy import select, delete, update, MetaData, Column, Integer, String, JSON, Float, Table, text, Text
from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, async_sessionmaker

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
    async_scoped_session = None

    def __init__(self,
                 url: AnyUrl | str,
                 metadata: MetaData,
                 *args, **kwargs):
        if isinstance(url, str):
            url = AnyUrl(url)
        super().__init__(url=url, *args, **kwargs)
        self.metadata = metadata
        self.engine = create_async_engine(
            self.url.unicode_string(),
            echo=IS_DEBUG,
            echo_pool=IS_DEBUG,
            hide_parameters=not IS_DEBUG,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    @asynccontextmanager
    async def context(self) -> AsyncGenerator:
        if not self.async_scoped_session:
            await self.new_session()
        session = self.async_scoped_session()  # # self.session是一个async_scoped_session
        try:
            yield session
        except BaseException as e:
            await self.async_scoped_session.rollback()
            self.logger.exception(e.__class__.__name__)
        finally:
            await self.async_scoped_session.commit()
            await self.async_scoped_session.remove()
            self.logger.debug(self.async_scoped_session.registry.registry)
            # del self.session

    # @UnitOfWork.timer(60)
    # async def check_async_scoped_session_registry_registry(self):
    #     self.logger.debug(len(self.async_scoped_session.registry.registry))

    async def new_session(self):
        # # https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncio-scoped-session
        async_session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        if not hasattr(self, 'session') or self.async_scoped_session is None:
            self.async_scoped_session = async_scoped_session(async_session_factory,
                                                             scopefunc=lambda: message.iid
                                                             if message else asyncio.current_task().get_name()
                                                             )  # # 一条message对应一个代理对象

    async def close_session(self):
        if self.async_scoped_session is not None:
            await self.async_scoped_session.close()

    async def create_all(self, metadata=None):
        async with self.engine.begin() as conn:
            if metadata:
                await conn.run_sync(metadata.create_all)
            else:
                await conn.run_sync(self.metadata.create_all)


class DatabasesUnitOfWork(UnitOfWork):

    async def context(self) -> AsyncGenerator:
        pass

    async def new_session(self):
        pass


class SqlAlchemyBaseProtocol(Protocol):
    unit_of_work: SqlAlchemyAsyncUnitOfWork

    @abc.abstractmethod
    async def _add(self, item: TypeVar, *args, **kwargs):
        ...

    @abc.abstractmethod
    async def _get(self, cls: Type, *args, **kwargs):
        ...  # pragma: no cover

    @abc.abstractmethod
    async def _delete(self, cls: Type, item_id, *args, **kwargs):
        ...

    @abc.abstractmethod
    async def _list(self, cls: Type, *args, **kwargs):
        ...

    @abc.abstractmethod
    async def _update(self, cls: Type, item_id, *args, **kwargs):
        ...

    @abc.abstractmethod
    async def _add_all(self, items: List[TypeVar], *args, **kwargs):
        ...

    @abc.abstractmethod
    async def _search(self, *args, **kwargs):
        ...

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


class SqlAlchemyProtocol(SqlAlchemyBaseProtocol):

    async def _add(self, item, *args, **kwargs):
        """
        stmt = (
        insert(user_table).
        values(name='username', fullname='Full Username')
        )
        如果orm定义的user和domain中定义的User模型的属性不同，上述方法不可用

        ！ greenlet_spawn方法报错，没有复现出来
        sqlalchemy.exc.IllegalStateChangeError: Method 'close()' can't be called here;
        method 'close()' is already in progress and this would cause an unexpected state change to
        <SessionTransactionState.CLOSED: 5>

        ! greenlet_spawn sqlalchemy.exc.MissingGreenlet: greenlet_spawn没有被调用；
        在这里不能调用await_only()。在一个意想不到的地方尝试过IO吗？
        (有关此错误的背景信息：https://sqlalche.me/e/14/xd2s)
        """

        async with self.unit_of_work.context() as session:
            session.add(item)
        return item

    async def _add_all(self, items, *args, **kwargs):
        async with self.unit_of_work.context() as session:
            session.add_all(items)
        return items

    async def _get(self, cls, *args, **kwargs):
        stmt = select(cls)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.unit_of_work.context() as session:
            result = await session.execute(stmt)
        return result.scalars().first()

    async def _list(self, cls, *args, **kwargs):
        stmt = select(cls)
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        async with self.unit_of_work.context() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def _update(self, cls: Table, item_id, *args, **kwargs):
        stmt = update(cls).where(cls.id.is_(item_id))
        stmt = stmt.values(update_time=time.time() * 1000, **kwargs)
        stmt = stmt.returning(cls)
        async with self.unit_of_work.context() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def _delete(self, cls: Table, item_id, *args, **kwargs):
        stmt = delete(cls).where(cls.id.is_(item_id))
        for column, value in kwargs.items():
            stmt = stmt.where(getattr(cls, column).is_(value))
        stmt = stmt.returning(cls)
        async with self.unit_of_work.context() as session:
            result = await session.execute(stmt)
        return result.scalars().all()

    async def _search(self, *args, **kwargs):
        query = text(kwargs['query'])
        async with self.unit_of_work.context() as session:
            result = await session.execute(query)
        return result.fetchall()
