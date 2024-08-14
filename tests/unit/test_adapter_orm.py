import pytest
from bollydog.adapters.orm import SqlAlchemyProtocol, SqlAlchemyAsyncUnitOfWork, map_imperatively
from pydantic import Field

from bollydog.models.base import BaseDomain


class Point(BaseDomain):
    x: int = Field(alias='x')
    y: int = Field(alias='y')
    title: str = Field(alias='title', max_length=50, default='title')


# map_imperatively(Point)


# point = Table(
#     'point', mapper_registry.metadata,
#     Column('id', Integer, primary_key=True, autoincrement=True),
#
#     Column('x', Integer),
#     Column('y', Integer),
#
# )
# mapper_registry.map_imperatively(Point, point)
# class Point(base):
#     __table__ = point

# @pytest.mark.asyncio
# async def test_adapter_orm():
#     unit_of_work = SqlAlchemyAsyncUnitOfWork(url='sqlite+aiosqlite:///:memory:')
#
#     async with unit_of_work:
#         await unit_of_work.create_all()
#         protocol = SqlAlchemyProtocol(unit_of_work=unit_of_work)
#         await protocol.add(Point(x=1, y=2))
#         u2 = await protocol.add(Point(x=3, y=4))
#         await protocol.add(Point(x=1, y=6))
#         user_list = await protocol.list(Point)
#         assert len(user_list) == 3
#         user_list = await protocol.list(Point, x=1)
#         assert len(user_list) == 2
#         assert await protocol.update(Point, item_id=u2['id'], y=5)
#         _u2 = await protocol.get(Point, id=u2['id'])
#         assert _u2.y == 5
#         res = await protocol.search(query='select id,x,y from point where x=1')
#         assert len(res) == 2
#         await protocol.delete(Point, item_id=u2['id'])
#         user_list = await protocol.list(Point)
#         assert len(user_list) == 2
