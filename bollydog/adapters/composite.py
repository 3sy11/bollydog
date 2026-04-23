"""Composite protocols — Protocol-holds-Protocol pattern.

CacheLayer:      memory + KVProtocol inner  → small data, JSON blob persistence
TableCacheLayer: memory + columnar DB inner → large data, structured row persistence, fast cold-start

Usage:
    # KV composite (small data)
    inner = SQLiteProtocol(path='data/cache.db')
    proto = CacheLayer(protocol=inner, flush_threshold=500)

    # Table composite (large data, fast cold-start)
    inner = DuckDBProtocol(url='data/ts.duckdb')
    proto = TableCacheLayer(protocol=inner, table='klines',
        key_columns=['symbol', 'interval'],
        value_columns=['ts', 'open', 'high', 'low', 'close', 'volume'],
        sort_by='ts')
"""
import asyncio
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
        # mode calls on_start BEFORE starting children; manually ensure inner protocol is ready
        if self.protocol is not None:
            await self.protocol.maybe_start()
        await self.load()

    async def on_stop(self) -> None:
        await self.flush()
        await super().on_stop()


class TableCacheLayer(KVProtocol):
    """Memory cache + columnar table backend for high-volume structured data.

    vs CacheLayer: inner protocol executes SQL (DuckDB/SQLite/SA) instead of KV JSON blobs.
    Cold-start: vectorized SELECT → grouped by key_columns → cache dict. No JSON ser/deser.
    Flush: batch INSERT with dedup (DELETE old + INSERT new) per dirty key.

    Exposes KVProtocol interface: get(compound_key) → list[dict], set(compound_key, rows).
    compound_key format: "val1:val2" matching key_columns order.
    """

    def __init__(self, protocol, table: str, key_columns: list, value_columns: list,
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
        super().__init__(protocol=protocol, **kwargs)

    def create(self):
        return self._cache

    def _parse_key(self, key: str) -> dict:
        parts = key.split(':')
        return dict(zip(self.key_columns, parts))

    def _make_key(self, row: dict) -> str:
        return ':'.join(str(row[c]) for c in self.key_columns)

    def _exec(self, sql, params=None):
        """Sync execute on inner protocol's adapter (DuckDB connection)."""
        if params:
            return self.protocol.adapter.execute(sql, params)
        return self.protocol.adapter.execute(sql)

    async def _run(self, fn, *a, **kw):
        return await asyncio.to_thread(fn, *a, **kw)

    # ─── KVProtocol interface ─────────────────────────────────

    async def get(self, key: str):
        if key in self._cache:
            return self._cache[key]
        kv = self._parse_key(key)
        where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
        vals = list(kv.values())
        cols = ', '.join(f'"{c}"' for c in self.value_columns)
        sql = f'SELECT {cols} FROM {self.table} WHERE {where}'
        if self.sort_by:
            sql += f' ORDER BY "{self.sort_by}"'
        def _q():
            try:
                return [dict(zip(self.value_columns, r)) for r in self._exec(sql, vals).fetchall()]
            except Exception:
                return None
        rows = await self._run(_q)
        if rows:
            self._cache[key] = rows
        return rows

    async def set(self, key: str, value, ttl: int = None):
        if self.sort_by and isinstance(value, list):
            value = sorted(value, key=lambda x: x.get(self.sort_by, 0))
        self._cache[key] = value
        self._dirty.add(key)
        if len(self._dirty) >= self.flush_threshold:
            await self.flush()

    async def remove(self, key: str):
        self._cache.pop(key, None)
        self._dirty.discard(key)
        kv = self._parse_key(key)
        where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
        await self._run(self._exec, f'DELETE FROM {self.table} WHERE {where}', list(kv.values()))

    async def exists(self, key: str) -> bool:
        if key in self._cache:
            return True
        kv = self._parse_key(key)
        where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
        def _q():
            return self._exec(f'SELECT 1 FROM {self.table} WHERE {where} LIMIT 1', list(kv.values())).fetchone()
        return await self._run(_q) is not None

    async def keys(self, pattern: str = '*') -> list:
        kcols = ', '.join(f'"{c}"' for c in self.key_columns)
        def _q():
            rows = self._exec(f'SELECT DISTINCT {kcols} FROM {self.table}').fetchall()
            return [':'.join(str(v) for v in r) for r in rows]
        backend_keys = set(await self._run(_q))
        if pattern == '*':
            return list(backend_keys | set(self._cache.keys()))
        prefix = pattern.rstrip('*')
        return list(backend_keys | {k for k in self._cache if k.startswith(prefix)})

    # ─── Load / Flush / Compact ───────────────────────────────

    async def load(self):
        """Cold-start: vectorized SELECT → group by key_columns → cache. No JSON."""
        kcols = ', '.join(f'"{c}"' for c in self.key_columns)
        vcols = ', '.join(f'"{c}"' for c in self.value_columns)
        sql = f'SELECT {kcols}, {vcols} FROM {self.table}'
        if self.sort_by:
            sql += f' ORDER BY {kcols}, "{self.sort_by}"'
        def _q():
            return self._exec(sql).fetchall()
        rows = await self._run(_q)
        for r in rows:
            row_dict = dict(zip(self.all_columns, r))
            key = self._make_key(row_dict)
            val = {c: row_dict[c] for c in self.value_columns}
            self._cache.setdefault(key, []).append(val)
        self.logger.info(f'TableCacheLayer loaded {len(self._cache)} keys ({len(rows)} rows) from {self.table}')

    async def flush(self):
        """Batch persist dirty keys: DELETE old rows + INSERT new rows per key."""
        if not self._dirty:
            return
        count = len(self._dirty)
        def _batch():
            for key in list(self._dirty):
                rows = self._cache.get(key)
                if rows is None:
                    continue
                kv = self._parse_key(key)
                where = ' AND '.join(f'"{c}"=?' for c in self.key_columns)
                self._exec(f'DELETE FROM {self.table} WHERE {where}', list(kv.values()))
                if not rows:
                    continue
                all_cols = ', '.join(f'"{c}"' for c in self.all_columns)
                placeholders = ', '.join('?' for _ in self.all_columns)
                insert_sql = f'INSERT INTO {self.table} ({all_cols}) VALUES ({placeholders})'
                batch = [[kv.get(c, r.get(c)) for c in self.all_columns] for r in rows]
                self._exec(f'{insert_sql}', batch[0])
                for b in batch[1:]:
                    self._exec(insert_sql, b)
        await self._run(_batch)
        self._dirty.clear()
        self.logger.info(f'TableCacheLayer flushed {count} keys → {self.table}')

    async def compact(self):
        if hasattr(self.protocol, 'compact'):
            await self.protocol.compact()

    async def _ensure_table(self):
        """Auto-create table if DDL provided."""
        if self.ddl:
            await self._run(self._exec, self.ddl)

    async def on_start(self) -> None:
        # mode calls on_start BEFORE starting children; manually ensure inner protocol is ready
        if self.protocol is not None:
            await self.protocol.maybe_start()
        await self._ensure_table()
        await self.load()

    async def on_stop(self) -> None:
        await self.flush()
        await super().on_stop()
