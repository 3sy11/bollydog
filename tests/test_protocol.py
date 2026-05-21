"""Layer 2: Protocol standalone tests — async, no Hub."""
import time


async def test_memory_set_get(memory_protocol):
    await memory_protocol.set('k1', {'a': 1})
    assert await memory_protocol.get('k1') == {'a': 1}

async def test_memory_remove(memory_protocol):
    await memory_protocol.set('k1', 'v')
    await memory_protocol.remove('k1')
    assert await memory_protocol.get('k1') is None

async def test_memory_exists(memory_protocol):
    assert not await memory_protocol.exists('k1')
    await memory_protocol.set('k1', 1)
    assert await memory_protocol.exists('k1')

async def test_memory_keys(memory_protocol):
    await memory_protocol.set('foo:1', 'a')
    await memory_protocol.set('foo:2', 'b')
    await memory_protocol.set('bar:1', 'c')
    all_keys = await memory_protocol.keys()
    assert set(all_keys) == {'foo:1', 'foo:2', 'bar:1'}
    foo_keys = await memory_protocol.keys('foo:*')
    assert set(foo_keys) == {'foo:1', 'foo:2'}

async def test_memory_batch_set_remove(memory_protocol):
    await memory_protocol.set_batch({'a': 1, 'b': 2, 'c': 3})
    assert await memory_protocol.get('b') == 2
    await memory_protocol.remove_batch(['a', 'c'])
    assert await memory_protocol.get('a') is None
    assert await memory_protocol.get('b') == 2
    assert await memory_protocol.get('c') is None


# ─── MemoryProtocol TTL ──────────────────────────────────────

async def test_memory_ttl_get_expired():
    from bollydog.adapters.memory import MemoryProtocol
    proto = MemoryProtocol()
    async with proto:
        await proto.set('tmp', 'val', ttl=0)
        time.sleep(0.01)
        assert await proto.get('tmp') is None

async def test_memory_ttl_exists_expired():
    from bollydog.adapters.memory import MemoryProtocol
    proto = MemoryProtocol()
    async with proto:
        await proto.set('tmp', 'val', ttl=0)
        time.sleep(0.01)
        assert not await proto.exists('tmp')

async def test_memory_ttl_keys_cleanup():
    from bollydog.adapters.memory import MemoryProtocol
    proto = MemoryProtocol()
    async with proto:
        await proto.set('keep', 'v1')
        await proto.set('expire', 'v2', ttl=0)
        time.sleep(0.01)
        keys = await proto.keys()
        assert 'keep' in keys
        assert 'expire' not in keys

async def test_memory_ttl_overwrite_removes_ttl():
    from bollydog.adapters.memory import MemoryProtocol
    proto = MemoryProtocol()
    async with proto:
        await proto.set('k', 'v', ttl=1)
        await proto.set('k', 'v2')
        assert 'k' not in proto._expiry


async def test_sqlite_standalone():
    """Protocol.__aenter__ triggers maybe_start(), no manual lifecycle needed."""
    from bollydog.adapters.memory import SQLiteProtocol
    proto = SQLiteProtocol(path=':memory:')
    async with proto:
        await proto.set('hello', {'msg': 'world'})
        assert await proto.get('hello') == {'msg': 'world'}
        assert await proto.exists('hello')
        keys = await proto.keys()
        assert 'hello' in keys


async def test_cache_layer_flush():
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.adapters.composite import CacheLayer
    inner = MemoryProtocol()
    layer = CacheLayer(flush_threshold=3)
    layer.add_dependency(inner)
    async with layer:
        await layer.set('a', 1)
        await layer.set('b', 2)
        assert await inner.get('a') is None  # not flushed yet
        await layer.set('c', 3)  # threshold hit → flush
        assert await inner.get('a') == 1
        assert await inner.get('b') == 2
        assert await inner.get('c') == 3


# ─── CacheLayer full coverage ────────────────────────────────

async def test_cache_layer_get_miss_fallback():
    """get cache miss → fallback to inner protocol."""
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.adapters.composite import CacheLayer
    inner = MemoryProtocol()
    layer = CacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await inner.set('deep', 'val')
        assert await layer.get('deep') == 'val'
        assert await layer.get('nope') is None

async def test_cache_layer_remove():
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.adapters.composite import CacheLayer
    inner = MemoryProtocol()
    layer = CacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await layer.set('x', 1)
        await layer.flush()
        await layer.remove('x')
        assert await layer.get('x') is None
        assert await inner.get('x') is None

async def test_cache_layer_exists():
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.adapters.composite import CacheLayer
    inner = MemoryProtocol()
    layer = CacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        assert not await layer.exists('z')
        await layer.set('z', 1)
        assert await layer.exists('z')
        await inner.set('only_inner', 2)
        assert await layer.exists('only_inner')

async def test_cache_layer_keys_pattern():
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.adapters.composite import CacheLayer
    inner = MemoryProtocol()
    layer = CacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await layer.set('foo:1', 'a')
        await layer.set('foo:2', 'b')
        await inner.set('foo:3', 'c')
        await layer.set('bar:1', 'd')
        foo_keys = set(await layer.keys('foo:*'))
        assert foo_keys == {'foo:1', 'foo:2', 'foo:3'}
        all_keys = set(await layer.keys())
        assert 'bar:1' in all_keys

async def test_cache_layer_compact():
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.adapters.composite import CacheLayer
    inner = MemoryProtocol()
    layer = CacheLayer(flush_threshold=100)
    layer.add_dependency(inner)
    async with layer:
        await layer.compact()


# ─── SQLite edge cases ───────────────────────────────────────

async def test_sqlite_keys_pattern():
    from bollydog.adapters.memory import SQLiteProtocol
    proto = SQLiteProtocol(path=':memory:')
    async with proto:
        await proto.set('user:1', 'a')
        await proto.set('user:2', 'b')
        await proto.set('item:1', 'c')
        matched = await proto.keys('user:*')
        assert set(matched) == {'user:1', 'user:2'}

async def test_sqlite_compact():
    from bollydog.adapters.memory import SQLiteProtocol
    proto = SQLiteProtocol(path=':memory:')
    async with proto:
        await proto.set('k', 'v')
        await proto.remove('k')
        await proto.compact()  # VACUUM
