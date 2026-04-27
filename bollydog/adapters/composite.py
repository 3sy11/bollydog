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
import asyncio
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
    """Memory cache + columnar table backend for high-volume structured data.

    on_start: init cache. on_started: ensure table + load (children ready).
    """

    def __init__(self, table: str, key_columns: list, value_columns: list,
                 sort_by: str = None, ddl: str = None, flush_threshold: int = 50, **kwargs):
        self._cache: dict = {}
        self._dirty: set = set()
        self.table = table
        self.key_columns = key_columns
        self.value_columns = value_columns
        self.all_columns = key_columns + value_columns
        self.sort_by = sort_by
        self.ddl = ddl
        self.flush_threshold = flush_threshold
        super().__init__(**kwargs)

    async def on_start(self) -> None:
        self.adapter = self._cache

    async def on_started(self) -> None:
        await self._ensure_table()
        await self.load()

    def _parse_key(self, key: str) -> dict:
        return dict(zip(self.key_columns, key.split(':')))

    def _make_key(self, row: dict) -> str:
        return ':'.join(str(row[c]) for c in self.key_columns)

    def _exec(self, sql, params=None):
        return self.protocol.adapter.execute(sql, params) if params else self.protocol.adapter.execute(sql)

    async def _run(self, fn, *a, **kw):
        return await asyncio.to_thread(fn, *a, **kw)

    async def get(self, key: str):
        if key in self._cache: return self._cache[key]
        kv = self._parse_key(key)
        where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
        cols = ', '.join(f'"{c}"' for c in self.value_columns)
        sql = f'SELECT {cols} FROM {self.table} WHERE {where}'
        if self.sort_by: sql += f' ORDER BY "{self.sort_by}"'
        def _q():
            try: return [dict(zip(self.value_columns, r)) for r in self._exec(sql, list(kv.values())).fetchall()]
            except Exception: return None
        rows = await self._run(_q)
        if rows: self._cache[key] = rows
        return rows

    async def set(self, key: str, value, ttl: int = None):
        if self.sort_by and isinstance(value, list):
            value = sorted(value, key=lambda x: x.get(self.sort_by, 0))
        self._cache[key] = value
        self._dirty.add(key)
        if len(self._dirty) >= self.flush_threshold: await self.flush()

    async def remove(self, key: str):
        self._cache.pop(key, None)
        self._dirty.discard(key)
        kv = self._parse_key(key)
        where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
        await self._run(self._exec, f'DELETE FROM {self.table} WHERE {where}', list(kv.values()))

    async def exists(self, key: str) -> bool:
        if key in self._cache: return True
        kv = self._parse_key(key)
        where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
        def _q(): return self._exec(f'SELECT 1 FROM {self.table} WHERE {where} LIMIT 1', list(kv.values())).fetchone()
        return await self._run(_q) is not None

    async def keys(self, pattern: str = '*') -> list:
        kcols = ', '.join(f'"{c}"' for c in self.key_columns)
        def _q():
            rows = self._exec(f'SELECT DISTINCT {kcols} FROM {self.table}').fetchall()
            return [':'.join(str(v) for v in r) for r in rows]
        backend_keys = set(await self._run(_q))
        if pattern == '*': return list(backend_keys | set(self._cache.keys()))
        prefix = pattern.rstrip('*')
        return list(backend_keys | {k for k in self._cache if k.startswith(prefix)})

    async def load(self):
        kcols = ', '.join(f'"{c}"' for c in self.key_columns)
        vcols = ', '.join(f'"{c}"' for c in self.value_columns)
        sql = f'SELECT {kcols}, {vcols} FROM {self.table}'
        if self.sort_by: sql += f' ORDER BY {kcols}, "{self.sort_by}"'
        rows = await self._run(lambda: self._exec(sql).fetchall())
        for r in rows:
            row_dict = dict(zip(self.all_columns, r))
            key = self._make_key(row_dict)
            self._cache.setdefault(key, []).append({c: row_dict[c] for c in self.value_columns})
        self.logger.info(f'TableCacheLayer loaded {len(self._cache)} keys ({len(rows)} rows) from {self.table}')

    async def flush(self):
        if not self._dirty: return
        count = len(self._dirty)
        def _batch():
            for key in list(self._dirty):
                rows = self._cache.get(key)
                if rows is None: continue
                kv = self._parse_key(key)
                where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
                self._exec(f'DELETE FROM {self.table} WHERE {where}', list(kv.values()))
                if not rows: continue
                all_cols = ', '.join(f'"{c}"' for c in self.all_columns)
                placeholders = ', '.join('?' for _ in self.all_columns)
                insert_sql = f'INSERT INTO {self.table} ({all_cols}) VALUES ({placeholders})'
                for r in rows:
                    self._exec(insert_sql, [kv.get(c, r.get(c)) for c in self.all_columns])
        await self._run(_batch)
        self._dirty.clear()
        self.logger.info(f'TableCacheLayer flushed {count} keys')

    async def compact(self):
        if hasattr(self.protocol, 'compact'): await self.protocol.compact()

    async def _ensure_table(self):
        if self.ddl: await self._run(self._exec, self.ddl)

    async def on_stop(self) -> None:
        await self.flush()
        await super().on_stop()
