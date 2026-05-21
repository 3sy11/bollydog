"""SqlAlchemyProtocol tests using SQLite in-memory (aiosqlite).

SqlAlchemyProtocol.__aenter__ is session-scoped (not lifecycle), so we
call maybe_start() / on_stop() explicitly to manage the engine lifecycle.
"""
from contextlib import asynccontextmanager
from sqlalchemy import MetaData, Table, Column, Integer, String, text, select, table, column


@asynccontextmanager
async def _lifecycle(proto):
    await proto.maybe_start()
    try: yield proto
    finally: await proto.on_stop()


async def test_sqlalchemy_start_execute_raw():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        result = await proto.execute_raw('SELECT 1')
        assert result[0][0] == 1

async def test_sqlalchemy_repr():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    assert 'SqlAlchemyProtocol' in repr(proto)
    assert 'sqlite' in repr(proto)

async def test_sqlalchemy_dialect_name():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        assert proto.dialect_name == 'sqlite'

async def test_sqlalchemy_create_all():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    meta = MetaData()
    Table('sa_test', meta, Column('id', Integer, primary_key=True), Column('name', String(50)))
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:', metadata=meta)
    async with _lifecycle(proto):
        await proto.create_all()
        result = await proto.execute_raw("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in result]
        assert 'sa_test' in tables

async def test_sqlalchemy_transaction():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        async with proto.transaction() as session:
            await session.execute(text('CREATE TABLE tx_test (k TEXT, v TEXT)'))
            await session.execute(text("INSERT INTO tx_test VALUES ('a', '1')"))
        result = await proto.execute_raw('SELECT * FROM tx_test')
        assert len(result) == 1

async def test_sqlalchemy_aenter_aexit():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        async with proto.transaction() as session:
            await session.execute(text('CREATE TABLE ctx_test (n INT)'))
        session = await proto.__aenter__()
        await session.execute(text('INSERT INTO ctx_test VALUES (42)'))
        await proto.__aexit__(None, None, None)
        result = await proto.execute_raw('SELECT * FROM ctx_test')
        assert result[0][0] == 42

async def test_sqlalchemy_compile():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        t = table('users', column('id'), column('name'))
        sql, params = proto.compile(select(t))
        assert 'SELECT' in sql.upper()
        assert 'users' in sql

async def test_sqlalchemy_compile_literal_binds():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        t = table('items', column('id'), column('price'))
        sql, params = proto.compile(select(t).where(column('id') == 1), literal_binds=True)
        assert '1' in sql
        assert params == {}

async def test_sqlalchemy_on_stop():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        await proto.execute_raw('SELECT 1')

async def test_sqlalchemy_search():
    from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol
    proto = SqlAlchemyProtocol(url='sqlite+aiosqlite:///:memory:')
    async with _lifecycle(proto):
        async with proto.transaction() as session:
            await session.execute(text('CREATE TABLE s (n INT)'))
            await session.execute(text("INSERT INTO s VALUES (1)"))
            await session.execute(text("INSERT INTO s VALUES (2)"))
        result = await proto.search(query='SELECT * FROM s')
        assert len(result) == 2
