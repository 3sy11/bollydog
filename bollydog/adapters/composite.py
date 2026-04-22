"""Composite protocols — Protocol-holds-Protocol pattern.

CacheLayer wraps any KVProtocol as inner `self.protocol`, providing:
  - Memory-first reads (zero-latency)
  - Dirty-tracking writes with threshold-triggered flush
  - on_start → load() cold-start recovery from inner protocol
  - on_stop  → flush() guaranteed persistence
  - manual compact() delegation

Usage:
    inner = SQLiteProtocol(path='data/cache.db')
    proto = CacheLayer(protocol=inner, flush_threshold=500)
    AppService(protocol=proto)  # inner lifecycle auto-managed via add_dependency
"""
from bollydog.adapters._base import KVProtocol


class CacheLayer(KVProtocol):
    """Memory cache + inner KVProtocol persistence (decorator pattern).

    self.protocol (inherited from Protocol base) is the persistence backend.
    All writes go to _cache + _dirty; flush() pushes dirty keys to self.protocol.
    All reads are cache-first; load() populates cache from self.protocol on startup.
    """

    def __init__(self, protocol: KVProtocol, flush_threshold: int = 100, **kwargs):
        self._cache: dict = {}
        self._dirty: set = set()
        self.flush_threshold = flush_threshold
        super().__init__(protocol=protocol, **kwargs)

    def create(self):
        return self._cache

    async def get(self, key: str):
        if key in self._cache:
            return self._cache[key]
        val = await self.protocol.get(key)
        if val is not None:
            self._cache[key] = val
        return val

    async def set(self, key: str, value, ttl: int = None):
        self._cache[key] = value
        self._dirty.add(key)
        if len(self._dirty) >= self.flush_threshold:
            await self.flush()

    async def remove(self, key: str):
        self._cache.pop(key, None)
        self._dirty.discard(key)
        await self.protocol.remove(key)

    async def exists(self, key: str) -> bool:
        return key in self._cache or await self.protocol.exists(key)

    async def keys(self, pattern: str = '*') -> list:
        backend_keys = set(await self.protocol.keys(pattern))
        if pattern == '*':
            return list(backend_keys | set(self._cache.keys()))
        prefix = pattern.rstrip('*')
        return list(backend_keys | {k for k in self._cache if k.startswith(prefix)})

    async def load(self):
        """Cold-start recovery: inner protocol → _cache."""
        for key in await self.protocol.keys():
            self._cache[key] = await self.protocol.get(key)
        self.logger.info(f'CacheLayer loaded {len(self._cache)} keys from {self.protocol.__class__.__name__}')

    async def flush(self):
        """Write dirty entries to inner protocol."""
        if not self._dirty:
            return
        count = len(self._dirty)
        for key in list(self._dirty):
            if key in self._cache:
                await self.protocol.set(key, self._cache[key])
        self._dirty.clear()
        self.logger.info(f'CacheLayer flushed {count} keys → {self.protocol.__class__.__name__}')

    async def compact(self):
        """Delegate to inner protocol if supported."""
        if hasattr(self.protocol, 'compact'):
            await self.protocol.compact()

    async def on_start(self) -> None:
        await self.load()

    async def on_stop(self) -> None:
        await self.flush()
        await super().on_stop()
