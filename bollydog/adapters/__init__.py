# Do NOT import from this package directly (e.g. `from bollydog.adapters import XxxProtocol`).
# Each protocol has optional third-party dependencies (redis, aiosqlite, duckdb, sqlalchemy, etc.)
# that may not be installed. Import the specific module you need instead:
#
#   from bollydog.adapters._base      import KVProtocol, CRUDProtocol, ...
#   from bollydog.adapters.memory     import MemoryProtocol, RedisProtocol, SQLiteProtocol
#   from bollydog.adapters.composite  import CacheLayer, TableCacheLayer
#   from bollydog.adapters.sqlalchemy import SqlAlchemyProtocol, DuckDBProtocol, ...
#   from bollydog.adapters.file       import LocalFileProtocol
#   from bollydog.adapters.elastic    import ElasticProtocol
#   from bollydog.adapters.graph      import Neo4jProtocol, NeuGProtocol
