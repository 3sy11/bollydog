"""TableCacheLayer tests — mirrors CacheLayer tests in test_protocol.py."""
from bollydog.adapters.memory import MemoryProtocol
from bollydog.adapters.composite import TableCacheLayer


async def test_table_cache_set_get():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await layer.set('k1', {'a': 1})
        assert await layer.get('k1') == {'a': 1}

async def test_table_cache_flush_on_threshold():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=2)
    layer.add_dependency(inner)
    async with layer:
        await layer.set('a', 10)
        assert await inner.get('a') is None
        await layer.set('b', 20)  # threshold hit → flush
        assert await inner.get('a') == 10
        assert await inner.get('b') == 20

async def test_table_cache_remove():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await layer.set('x', 'v')
        await layer.flush()
        await layer.remove('x')
        assert await layer.get('x') is None
        assert await inner.get('x') is None

async def test_table_cache_exists():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        assert not await layer.exists('z')
        await layer.set('z', 99)
        assert await layer.exists('z')

async def test_table_cache_keys():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await inner.set('old', 1)
        await layer.set('new', 2)
        all_keys = set(await layer.keys())
        assert 'old' in all_keys
        assert 'new' in all_keys

async def test_table_cache_sort_by():
    inner = MemoryProtocol()
    layer = TableCacheLayer(sort_by='ts', flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        data = [{'ts': 3}, {'ts': 1}, {'ts': 2}]
        await layer.set('sorted', data)
        result = await layer.get('sorted')
        assert [r['ts'] for r in result] == [1, 2, 3]

async def test_table_cache_load_from_inner():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with inner:
        await inner.set('pre1', 'v1')
        await inner.set('pre2', 'v2')
    async with layer:
        assert await layer.get('pre1') == 'v1'
        assert await layer.get('pre2') == 'v2'

async def test_table_cache_compact():
    inner = MemoryProtocol()
    layer = TableCacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await layer.compact()  # no-op if inner has no compact, should not raise
