"""Extra adapter tests — Graph init, DialectMixin, BatchMixin, base ABC defaults."""
import pytest
from unittest.mock import MagicMock, AsyncMock


# ─── Graph protocol init (no real driver) ─────────────────────

def test_neo4j_protocol_init():
    from bollydog.adapters.graph import Neo4jProtocol
    proto = Neo4jProtocol(url='bolt://localhost:7687', auth=('neo4j', 'test'))
    assert proto.url == 'bolt://localhost:7687'
    assert proto.auth == ('neo4j', 'test')

def test_neug_protocol_init():
    from bollydog.adapters.graph import NeuGProtocol
    proto = NeuGProtocol(cluster_type='hosts', num_workers=2)
    assert proto.cluster_type == 'hosts'
    assert proto.num_workers == 2
    assert proto._session is None

async def test_neug_execute_requires_graph():
    from bollydog.adapters.graph import NeuGProtocol
    proto = NeuGProtocol()
    proto._session = MagicMock()
    with pytest.raises(ValueError, match='graph'):
        await proto.execute('MATCH (n) RETURN n')

async def test_neug_run_algorithm_missing():
    from bollydog.adapters.graph import NeuGProtocol
    proto = NeuGProtocol()
    proto._session = MagicMock()
    import importlib
    mock_gs = MagicMock(spec=[])  # empty spec → getattr returns AttributeError
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(__import__('sys').modules, 'graphscope', mock_gs)
        with pytest.raises(AttributeError, match='no algorithm'):
            await proto.run_algorithm('nonexistent_algo', MagicMock())

async def test_neo4j_on_stop_none():
    from bollydog.adapters.graph import Neo4jProtocol
    proto = Neo4jProtocol(url='bolt://localhost', auth=('a', 'b'))
    proto.adapter = None
    await proto.on_stop()  # should not raise

async def test_neug_on_stop_cleans_session():
    from bollydog.adapters.graph import NeuGProtocol
    proto = NeuGProtocol()
    mock_session = MagicMock()
    proto._session = mock_session
    await proto.on_stop()
    mock_session.close.assert_called_once()
    assert proto._session is None


# ─── KVProtocol ABC default implementations ──────────────────

async def test_kv_exists_default():
    """KVProtocol.exists default: returns (get(key) is not None)."""
    from bollydog.adapters._base import KVProtocol
    class _Kv(KVProtocol):
        async def on_start(self): self.adapter = {}
        async def get(self, key): return self.adapter.get(key)
        async def set(self, key, value, ttl=None): self.adapter[key] = value
        async def remove(self, key): self.adapter.pop(key, None)
    proto = _Kv()
    async with proto:
        assert not await proto.exists('x')
        await proto.set('x', 1)
        assert await proto.exists('x')

async def test_kv_keys_not_implemented():
    from bollydog.adapters._base import KVProtocol
    class _Kv(KVProtocol):
        async def on_start(self): self.adapter = {}
        async def get(self, key): return None
        async def set(self, key, value, ttl=None): pass
        async def remove(self, key): pass
    proto = _Kv()
    async with proto:
        with pytest.raises(NotImplementedError):
            await proto.keys()

async def test_kv_batch_default_loop():
    """Default set_batch/remove_batch loop over items."""
    from bollydog.adapters._base import KVProtocol
    class _Kv(KVProtocol):
        async def on_start(self): self.adapter = {}
        async def get(self, key): return self.adapter.get(key)
        async def set(self, key, value, ttl=None): self.adapter[key] = value
        async def remove(self, key): self.adapter.pop(key, None)
    proto = _Kv()
    async with proto:
        await proto.set_batch({'a': 1, 'b': 2})
        assert await proto.get('a') == 1
        await proto.remove_batch(['a'])
        assert await proto.get('a') is None


# ─── DialectMixin ─────────────────────────────────────────────

def test_dialect_mixin_resolve():
    from bollydog.adapters._base import DialectMixin
    mixin = DialectMixin()
    dialect = mixin._resolve_dialect('sqlite')
    assert dialect is not None

def test_dialect_mixin_compile():
    from bollydog.adapters._base import DialectMixin
    from sqlalchemy import select, table, column
    mixin = DialectMixin()
    mixin._dialect = mixin._resolve_dialect('sqlite')
    sql, params = mixin.compile(select(table('t', column('id'))))
    assert 'SELECT' in sql.upper()


# ─── StreamMixin / TransactionMixin defaults ──────────────────

async def test_stream_mixin_not_implemented():
    from bollydog.adapters._base import StreamMixin
    mixin = StreamMixin()
    with pytest.raises(NotImplementedError):
        await mixin.stream()

async def test_transaction_mixin_not_implemented():
    from bollydog.adapters._base import TransactionMixin
    mixin = TransactionMixin()
    with pytest.raises(NotImplementedError):
        async with mixin.transaction():
            pass


# ─── CRUDProtocol.count default ──────────────────────────────

async def test_crud_count_default():
    from bollydog.adapters._base import CRUDProtocol
    class _Crud(CRUDProtocol):
        async def on_start(self): self.adapter = True
        async def add(self, item, **ctx): pass
        async def add_all(self, items, **ctx): pass
        async def get(self, **query): return None
        async def list(self, **query): return [1, 2, 3]
        async def update(self, query, data): pass
        async def delete(self, **query): pass
    proto = _Crud()
    async with proto:
        assert await proto.count() == 3


# ─── Utils ────────────────────────────────────────────────────

def test_get_hostname():
    from bollydog.utils.base import get_hostname
    h = get_hostname()
    assert isinstance(h, str)
    assert len(h) > 0

def test_get_repository_version():
    from bollydog.utils.base import get_repository_version
    v = get_repository_version()
    assert isinstance(v, str)
