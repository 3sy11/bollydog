import pytest
import sqlalchemy
import sqlmodel
from sqlalchemy import select, insert, update, delete

from bollydog.adapters.rdb import SQLModelDomain
from bollydog.adapters.rdb import SqlAlchemyProtocol, SqlAlchemyAsyncUnitOfWork
from bollydog.adapters.rdb import DuckDBUnitOfWork

metadata = sqlalchemy.MetaData()


class Point(SQLModelDomain, table=True):
    metadata = metadata
    x: int = sqlmodel.Field(alias='x')
    y: int = sqlmodel.Field(alias='y')
    title: str = sqlmodel.Field(alias='title', max_length=50, default='no title')


# @pytest.mark.asyncio
# async def test_adapter_rdb_sqlalchemy_unit_of_work():
#     unit_of_work = SqlAlchemyAsyncUnitOfWork(url='sqlite+aiosqlite:///:memory:', metadata=metadata, echo=True)
#     unit_of_work.create()
#     await unit_of_work.create_all(metadata)
#
#     async with unit_of_work:
#         protocol = SqlAlchemyProtocol(unit_of_work=unit_of_work)
#         await protocol.add(Point(x=1, y=2))
#         u2 = await protocol.add(Point(x=3, y=4))
#         await protocol.add(Point(x=1, y=6))
#         user_list = await protocol.list(Point)
#         assert len(user_list) == 3
#         user_list = await protocol.list(Point, x=1)
#         assert len(user_list) == 2
#         assert await protocol.update(Point, item_id=u2.id, y=5)
#         _u2 = await protocol.get(Point, id=u2.id)
#         assert _u2['y'] == 5
#         res = await protocol.search(query='select id,x,y from point where x=1')
#         assert len(res) == 2
#         await protocol.delete(Point, item_id=u2.id)
#         user_list = await protocol.list(Point)
#         assert len(user_list) == 2


@pytest.mark.asyncio
async def test_adapter_rdb_duckdb_unit_of_work():
    unit_of_work = DuckDBUnitOfWork(url=':memory:', metadata=metadata)
    unit_of_work.create()

    async with unit_of_work.connect() as conn:
        await unit_of_work.create_all(metadata)
        # 添加数据
        points = [
            Point(x=1, y=2, title='Point A'),
            Point(x=3, y=4, title='Point B'),
            Point(x=1, y=6, title='Point C')
        ]
        insert_stmt = insert(Point).values([p.model_dump() for p in points])
        sql = str(insert_stmt.compile(compile_kwargs={"literal_binds": True}))
        conn.execute(sql)

        # 测试查询
        select_all_stmt = select(Point)
        result = conn.execute(str(select_all_stmt.compile(compile_kwargs={"literal_binds": True}))).fetchall()
        assert len(result) == 3

        select_x1_stmt = select(Point).where(Point.x == 1)
        result = conn.execute(str(select_x1_stmt.compile(compile_kwargs={"literal_binds": True}))).fetchall()
        assert len(result) == 2

        # 测试更新
        update_stmt = update(Point).where(Point.x == 3).values(y=5)
        conn.execute(str(update_stmt.compile(compile_kwargs={"literal_binds": True})))

        select_updated_stmt = select(Point.y).where(Point.x == 3)
        result = conn.execute(str(select_updated_stmt.compile(compile_kwargs={"literal_binds": True}))).fetchone()
        assert result[0] == 5

        # 测试删除
        delete_stmt = delete(Point).where(Point.x == 3)
        conn.execute(str(delete_stmt.compile(compile_kwargs={"literal_binds": True})))

        select_after_delete_stmt = select(Point)
        result = conn.execute(str(select_after_delete_stmt.compile(compile_kwargs={"literal_binds": True}))).fetchall()
        assert len(result) == 2
