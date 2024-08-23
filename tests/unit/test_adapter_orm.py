import pytest
import sqlalchemy
import sqlmodel

from bollydog.adapters.rdb import SqlAlchemyProtocol, SqlAlchemyAsyncUnitOfWork
from bollydog.adapters.rdb import SQLModelDomain

metadata = sqlalchemy.MetaData()

class Point(SQLModelDomain, table=True):
    metadata = metadata
    x: int = sqlmodel.Field(alias='x')
    y: int = sqlmodel.Field(alias='y')
    title: str = sqlmodel.Field(alias='title', max_length=50, default='no title')


@pytest.mark.asyncio
async def test_adapter_rdb_sqlalchemy_unit_of_work():
    unit_of_work = SqlAlchemyAsyncUnitOfWork(url='sqlite+aiosqlite:///:memory:', metadata=metadata, echo=True)
    await unit_of_work.create_all(metadata)

    async with unit_of_work:
        protocol = SqlAlchemyProtocol(unit_of_work=unit_of_work)
        await protocol.add(Point(x=1, y=2))
        u2 = await protocol.add(Point(x=3, y=4))
        await protocol.add(Point(x=1, y=6))
        user_list = await protocol.list(Point)
        assert len(user_list) == 3
        user_list = await protocol.list(Point, x=1)
        assert len(user_list) == 2
        assert await protocol.update(Point, item_id=u2.id, y=5)
        _u2 = await protocol.get(Point, id=u2.id)
        assert _u2['y'] == 5
        res = await protocol.search(query='select id,x,y from point where x=1')
        assert len(res) == 2
        await protocol.delete(Point, item_id=u2.id)
        user_list = await protocol.list(Point)
        assert len(user_list) == 2
