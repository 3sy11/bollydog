"""Composite protocols — Protocol-holds-Protocol pattern.

CacheLayer:      memory + KVProtocol inner  -> small data, JSON blob persistence
TableCacheLayer: memory + columnar DB inner -> large data, structured row persistence, fast cold-start

Usage (via TOML):
    [myapp.service.MyService.protocol]
    module = "bollydog.adapters.composite.CacheLayer"
    flush_threshold = 500

    [myapp.service.MyService.protocol.protocol]
    module = "bollydog.adapters.memory.SQLiteProtocol"
    path = "data/cache.db"
"""
from bollydog.adapters._base import KVProtocol


class CacheLayer(KVProtocol):
    """Memory cache + inner KVProtocol persistence (decorator pattern).

    self.protocol is the persistence backend (bound via add_dependency).
    on_start: init cache. on_started: load from inner (children ready by then).
    """

    def __init__(self, flush_threshold: int = 100, **kwargs):
        self._cache: dict = {}
        self._dirty: set = set()
        self.flush_threshold = flush_threshold
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        self.adapter = self._cache

    async def on_started(self) -> None:
        await self.load()

    async def get(self, key: str):
        if key in self._cache: return self._cache[key]
        val = await self.protocol.get(key)
        if val is not None: self._cache[key] = val
        return val

    async def set(self, key: str, value, ttl: int = None):
        self._cache[key] = value
        self._dirty.add(key)
        if len(self._dirty) >= self.flush_threshold: await self.flush()

    async def remove(self, key: str):
        self._cache.pop(key, None)
        self._dirty.discard(key)
        await self.protocol.remove(key)

    async def exists(self, key: str) -> bool:
        return key in self._cache or await self.protocol.exists(key)

    async def keys(self, pattern: str = '*') -> list:
        backend_keys = set(await self.protocol.keys(pattern))
        if pattern == '*': return list(backend_keys | set(self._cache.keys()))
        prefix = pattern.rstrip('*')
        return list(backend_keys | {k for k in self._cache if k.startswith(prefix)})

    async def load(self):
        for key in await self.protocol.keys():
            self._cache[key] = await self.protocol.get(key)
        self.logger.info(f'CacheLayer loaded {len(self._cache)} keys from {self.protocol.__class__.__name__}')

    async def flush(self):
        if not self._dirty: return
        count = len(self._dirty)
        for key in list(self._dirty):
            if key in self._cache: await self.protocol.set(key, self._cache[key])
        self._dirty.clear()
        self.logger.info(f'CacheLayer flushed {count} keys')

    async def compact(self):
        if hasattr(self.protocol, 'compact'): await self.protocol.compact()

    async def on_stop(self) -> None:
        await self.flush()
        await super().on_stop()


class TableCacheLayer(KVProtocol):
    """Memory cache + KVProtocol backend for structured row data.

    All persistence goes through self.protocol KVProtocol API (get/set/remove/keys).
    The inner protocol owns schema and storage format; this layer only manages
    composite keys and in-memory cache with dirty tracking.
    """

    def __init__(self, sort_by: str = None, flush_threshold: int = 50, **kwargs):
        self._cache: dict = {}
        self._dirty: set = set()
        self.sort_by = sort_by
        self.flush_threshold = flush_threshold
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        self.adapter = self._cache

    async def on_started(self) -> None:
        await self.load()

    async def get(self, key: str):
        if key in self._cache: return self._cache[key]
        val = await self.protocol.get(key)
        if val is not None: self._cache[key] = val
        return val

    async def set(self, key: str, value, ttl: int = None):
        if self.sort_by and isinstance(value, list):
            value = sorted(value, key=lambda x: x.get(self.sort_by, 0))
        self._cache[key] = value
        self._dirty.add(key)
        if len(self._dirty) >= self.flush_threshold: await self.flush()

    async def remove(self, key: str):
        self._cache.pop(key, None)
        self._dirty.discard(key)
        await self.protocol.remove(key)

    async def exists(self, key: str) -> bool:
        return key in self._cache or await self.protocol.exists(key)

    async def keys(self, pattern: str = '*') -> list:
        backend_keys = set(await self.protocol.keys(pattern))
        if pattern == '*': return list(backend_keys | set(self._cache.keys()))
        prefix = pattern.rstrip('*')
        return list(backend_keys | {k for k in self._cache if k.startswith(prefix)})

    async def load(self):
        for key in await self.protocol.keys():
            self._cache[key] = await self.protocol.get(key)
        self.logger.info(f'TableCacheLayer loaded {len(self._cache)} keys from {self.protocol.__class__.__name__}')

    async def flush(self):
        if not self._dirty: return
        count = len(self._dirty)
        dirty_keys = list(self._dirty)
        await self.protocol.remove_batch(dirty_keys)
        await self.protocol.set_batch({k: self._cache[k] for k in dirty_keys if k in self._cache})
        self._dirty.clear()
        self.logger.info(f'TableCacheLayer flushed {count} keys')

    async def compact(self):
        if hasattr(self.protocol, 'compact'): await self.protocol.compact()

    async def on_stop(self) -> None:
        await self.flush()
        await super().on_stop()
