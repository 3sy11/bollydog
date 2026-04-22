import json
import time
from typing import Optional
from bollydog.models.protocol import Protocol
from bollydog.adapters._base import KVProtocol


class NoneProtocol(Protocol):
    def create(self):
        return True


class LogProtocol(Protocol):
    def create(self):
        return True


class MemoryProtocol(KVProtocol):
    """In-memory dict KV with optional lazy TTL."""

    def __init__(self, **kwargs):
        self._expiry: dict[str, float] = {}
        super().__init__(**kwargs)

    def create(self):
        return {}

    def _check_expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is not None and time.time() > exp:
            self.adapter.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    async def get(self, key: str):
        if self._check_expired(key):
            return None
        return self.adapter.get(key)

    async def set(self, key: str, value, ttl: int = None):
        self.adapter[key] = value
        if ttl is not None:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            del self._expiry[key]

    async def remove(self, key: str):
        self.adapter.pop(key, None)
        self._expiry.pop(key, None)

    async def exists(self, key: str) -> bool:
        if self._check_expired(key):
            return False
        return key in self.adapter

    async def keys(self, pattern: str = '*') -> list:
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if now > exp]
        for k in expired:
            self.adapter.pop(k, None)
            self._expiry.pop(k, None)
        if pattern == '*':
            return list(self.adapter.keys())
        prefix = pattern.rstrip('*')
        return [k for k in self.adapter if k.startswith(prefix)]


# ─── RedisProtocol ────────────────────────────────────────────

class RedisProtocol(KVProtocol):

    def __init__(self, url: str = 'redis://localhost', **kwargs):
        self.url = url
        super().__init__(**kwargs)

    def create(self):
        from redis.asyncio import from_url
        return from_url(self.url)

    async def get(self, key: str) -> Optional[dict]:
        data = await self.adapter.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value, ttl: int = 3600):
        await self.adapter.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)

    async def remove(self, key: str):
        await self.adapter.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.adapter.exists(key))

    async def keys(self, pattern: str = '*') -> list:
        result = []
        async for key in self.adapter.scan_iter(match=pattern):
            result.append(key.decode() if isinstance(key, bytes) else key)
        return result

    def delete(self):
        pass


# ─── SQLiteProtocol ───────────────────────────────────────────

class SQLiteProtocol(KVProtocol):
    """SQLite as KV store: kv(key TEXT PK, value TEXT, updated_at REAL)."""

    def __init__(self, path: str = ':memory:', table: str = 'kv', **kwargs):
        self.path = path
        self.table = table
        self._db = None
        super().__init__(**kwargs)

    def create(self):
        return self.path

    async def _conn(self):
        if self._db is None:
            import aiosqlite
            self._db = await aiosqlite.connect(self.path)
        return self._db

    async def on_start(self) -> None:
        db = await self._conn()
        await db.execute(f'CREATE TABLE IF NOT EXISTS {self.table} (key TEXT PRIMARY KEY, value TEXT, updated_at REAL)')
        await db.commit()

    async def get(self, key: str):
        db = await self._conn()
        async with db.execute(f'SELECT value FROM {self.table} WHERE key=?', (key,)) as cur:
            row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def set(self, key: str, value, ttl: int = None):
        db = await self._conn()
        await db.execute(f'INSERT OR REPLACE INTO {self.table} (key, value, updated_at) VALUES (?, ?, ?)',
                         (key, json.dumps(value, ensure_ascii=False), time.time()))
        await db.commit()

    async def remove(self, key: str):
        db = await self._conn()
        await db.execute(f'DELETE FROM {self.table} WHERE key=?', (key,))
        await db.commit()

    async def exists(self, key: str) -> bool:
        db = await self._conn()
        async with db.execute(f'SELECT 1 FROM {self.table} WHERE key=? LIMIT 1', (key,)) as cur:
            return await cur.fetchone() is not None

    async def keys(self, pattern: str = '*') -> list:
        db = await self._conn()
        if pattern == '*':
            async with db.execute(f'SELECT key FROM {self.table}') as cur:
                return [r[0] for r in await cur.fetchall()]
        async with db.execute(f'SELECT key FROM {self.table} WHERE key LIKE ?', (pattern.replace('*', '%'),)) as cur:
            return [r[0] for r in await cur.fetchall()]

    async def compact(self):
        db = await self._conn()
        await db.execute('VACUUM')
        await db.commit()

    async def on_stop(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
        await super().on_stop()
