"""DuckDB in-memory tests — no external database needed."""


async def test_duckdb_start_and_query():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('CREATE TABLE t1 (id INT, name VARCHAR)')
        await proto.execute_raw("INSERT INTO t1 VALUES (1, 'alice'), (2, 'bob')")
        rows = await proto.list(query='SELECT * FROM t1 ORDER BY id')
        assert len(rows) == 2
        assert rows[0] == (1, 'alice')

async def test_duckdb_add_scalar():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('CREATE TABLE items (val INT)')
        await proto.add(42, table='items')
        row = await proto.get(query='SELECT * FROM items LIMIT 1')
        assert row[0] == 42

async def test_duckdb_list():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('CREATE TABLE nums (n INT)')
        for i in range(5):
            await proto.execute_raw(f'INSERT INTO nums VALUES ({i})')
        rows = await proto.list(query='SELECT * FROM nums ORDER BY n')
        assert len(rows) == 5

async def test_duckdb_update():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('CREATE TABLE kv (k VARCHAR, v INT)')
        await proto.execute_raw("INSERT INTO kv VALUES ('a', 1)")
        await proto.update({'query': "UPDATE kv SET v=2 WHERE k='a'"}, {})
        rows = await proto.list(query="SELECT v FROM kv WHERE k='a'")
        assert rows[0][0] == 2

async def test_duckdb_delete():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('CREATE TABLE d (id INT)')
        await proto.execute_raw('INSERT INTO d VALUES (1), (2)')
        await proto.delete(query='DELETE FROM d WHERE id=1')
        rows = await proto.list(query='SELECT * FROM d')
        assert len(rows) == 1

async def test_duckdb_repr():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    assert 'DuckDBProtocol' in repr(proto)
    assert ':memory:' in repr(proto)

async def test_duckdb_create_all_with_metadata():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    from sqlalchemy import MetaData, Table, Column, Integer, String
    meta = MetaData()
    Table('test_duck', meta, Column('id', Integer, primary_key=True), Column('name', String(50)))
    proto = DuckDBProtocol(url=':memory:', metadata=meta)
    async with proto:
        proto.create_all()
        rows = await proto.list(query='SELECT * FROM test_duck')
        assert rows == []

async def test_duckdb_create_all_skip_existing():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    from sqlalchemy import MetaData, Table, Column, Integer
    meta = MetaData()
    Table('dup', meta, Column('id', Integer, primary_key=True))
    proto = DuckDBProtocol(url=':memory:', metadata=meta)
    async with proto:
        proto.create_all()
        proto.create_all()  # second call should skip existing

async def test_duckdb_create_all_no_metadata():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        proto.create_all()  # no-op when no metadata

async def test_duckdb_add_all():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('CREATE TABLE multi (val INT)')
        await proto.add_all([10, 20, 30], table='multi')
        rows = await proto.list(query='SELECT * FROM multi ORDER BY val')
        assert len(rows) == 3

async def test_duckdb_on_stop():
    from bollydog.adapters.sqlalchemy import DuckDBProtocol
    proto = DuckDBProtocol(url=':memory:')
    async with proto:
        await proto.execute_raw('SELECT 1')
