---
name: bollydog-framework
description: bollydog AI quick-ref — pipeline (_fire/_publish), Command loading, destination as Exchange topic, Exchange/Queue, data/events, globals, Command/Service boundary.
---

# Bollydog — AI Quick Reference

Details in [README.md](../README.md).

## Concepts

`BaseCommand`(`__call__`) → `Hub` dispatches; `AppService`(`router_mapping` HTTP routes, optional `protocol`, `subscribe` patterns); **`destination`** = 3-part **topic** (`domain.ServiceAlias.CommandAlias`), unbound defaults to `_._.CommandAlias`.

## Pipeline

`Hub.dispatch(message)` routes by type and qos:

| Path | Type | Routing | Queue | Publish |
|------|------|---------|-------|---------|
| Event | `BaseEvent` | `create_task(_fire)` | No | Yes |
| Command qos=0 | `BaseCommand` | `create_task(_fire)` | No | Yes |
| Command qos=1 | `BaseCommand` | `queue.put` → consumer | Yes | Yes |

### Execution methods

- `_fire(msg)`: `async with _with_context(msg)` → `_execute(msg, runner)` → `_publish(msg)`. Shared by Event and Command qos=0.
- `_execute(msg, runner)`: runs before-hooks → runner → after-hooks. All three paths (`_fire`, `_process_queued`, `execute`) go through `_execute`.
- `_run`: coroutine with retry loop. Pure execution, no context management.
- `_run_gen`: async generator, no retry. Handles `yield Command` (dispatch + send result back), `yield [cmd, ...]` (parallel dispatch + gather), and `yield value` (stream to state).
- `_process_queued(msg)`: `async with _with_context(msg)` → `_execute` → `ack`/`nack` → `_publish(msg)`.
- `execute(msg)`: CLI direct mode. `async with _with_context(msg)` → `_execute`. No elevate, no queue.
- `_with_context`: asynccontextmanager — push `app`, `protocol`, `message` globals for the request scope.

### _publish

`Hub._publish(msg)` matches `type(msg).destination` via `exchange.match(topic)`:
- **Command class** handler → instantiate, `add_event(msg)`, dispatch

Runs **inside** `_with_context`, so handler Commands inherit trace correctly.

## Exchange (pub/sub, pure router)

- `exchange.subscribe(topic, handler)`: handler is **Command class** only.
- `exchange.match(topic) -> set`: returns matched handlers (exact + pattern).
- Exchange does **not** instantiate Commands or create tasks. Hub._publish handles that.
- AMQP-style wildcards: `*` = one segment, `#` = zero or more.

## data & events

`BaseCommand.data: dict`, general-purpose data field. `events` sub-key stores list of dict:

- `cmd.add_event(event)` → append `event.model_dump()`
- `cmd.get_event()` → latest `[-1]`; `get_event(0)` → earliest

Exchange handler Commands retrieve trigger event via `self.get_event()`.

## destination (topic)

- **Routing**: `Hub._resolve_app` takes first two segments `domain.ServiceAlias`; `_._` = unbound.
- **Fast-fail**: non-`_._` destination pointing to unregistered service raises `DestinationNotFoundError`.
- **Exchange**: `_publish` uses `destination` as topic for pattern matching.

## hub.get_service

`hub.get_service(cls_or_key, *, required=True)` — retrieve registered `AppService` by class, instance, or string key. Raises `ServiceNotFoundError` if `required=True` and not found.

## Command loading: two paths

- **Auto-discover**: project root `commands/`, `smart_import` during `get_apps`. Default `destination = '_._.CommandAlias'`.
- **Explicit binding**: `AppService.commands` or YAML. `_load_commands` rewrites `_._` prefix to `{domain}.{alias}.{CommandAlias}`.

## Subscriptions

- `AppService.subscribe: ClassVar[dict]` — `topic_pattern: CommandClass` only.
- YAML overridable. Registered in `Hub.on_started` to `exchange`.

## Command / AppService boundary (strict)

### Principles

- **Command** = thin orchestration only (scheduling and glue); no owned state; do not reach into internal service structure.
- **AppService** = resource owner; expose **business methods** for Commands; inner sub-services (e.g. SwingService, FibService) must stay invisible to Commands.
- **Protocol** = environment abstraction: production `SqlAlchemyProtocol` / `RedisProtocol`; tests `MemoryProtocol` / `NoneProtocol`.
- Commands use `globals.app` (pushed by `_with_context` from `destination`) for the owning `AppService`. **Do not** use `app.child_service.xxx`.
- Cross-domain: `hub.dispatch(sub_cmd)` or `yield sub_cmd` (async-gen orchestration); do not use `hub.get_service` to grab other domains’ services ad hoc.

### Three Command patterns (follow strictly)

**1. Pure compute Command — no `app`; unit-testable in isolation**

```python
class ComputeSwingFeatures(BaseCommand):
    destination = "timing.AnalysisEngine.ComputeSwingFeatures"
    klines: list; config: dict
    async def __call__(self):
        return compute_swing_features(self.klines, self.config)
```

Test: `cmd = ComputeSwingFeatures(klines=data, config={...}); result = await cmd()` — no Hub required.

**2. Orchestration Command — `app` business methods + child Commands + `protocol` persistence**

```python
class OnCacheIngested(BaseCommand):
    destination = "timing.AnalysisEngine.OnCacheIngested"
    async def __call__(self):
        klines = ...  # from upstream event or dispatch GetKlines
        result = app.recompute_fib(sym, interval, klines)  # method on AppService
        await protocol.set(f"{sym}:{interval}", result)    # persistence via protocol
        await hub.emit(FibLinesUpdated(...))                # emit event
```

Encapsulate orchestration on `AppService`:

```python
class AnalysisEngine(AppService):
    def recompute_fib(self, symbol, interval, klines):
        ch, cl = self.swing.compute_features(klines, self.config)
        self.swing.set_cache(symbol, interval, ch, cl)
        result = self.fib.compute_and_store(symbol, interval, ch, cl, self.config)
        self.detector.reset(symbol, interval)
        return result
```

Test: mock `app.recompute_fib` return value + `MemoryProtocol`; no real sub-services or DB.

**3. Async-gen orchestration — chain child Commands with `yield`; parallel with `yield [...]`**

```python
class FullPipeline(BaseCommand):
    async def __call__(self):
        # sequential
        gk = GetKlines(symbol=self.symbol, interval=self.interval, qos=0)
        yield gk
        klines = gk.state.result()
        # parallel fan-out/fan-in
        results = yield [ComputeSwing(klines=klines), ComputeFib(klines=klines)]
        await protocol.set(f"{self.symbol}:{self.interval}", results)
```

`yield Command` = sequential; `yield [cmd, cmd, ...]` = parallel dispatch + gather.
Each yielded child Command is testable alone; the parent is glue only.

### Testing strategy

| Layer | Production | Tests |
|-------|------------|-------|
| Protocol | `SqlAlchemyProtocol`, `RedisProtocol` | `MemoryProtocol`, `NoneProtocol` |
| AppService methods | real implementation | mock return values |
| Pure compute Command | `await cmd()` directly | same — no Hub |
| Orchestration Command | full Hub | mock `app.method` + `MemoryProtocol`, or assert orchestration order only |

### Do not

- In Commands: `app.swing.xxx` / `app.fib.xxx` — reaching into inner sub-services.
- In Commands: hard-coded DB URLs or file paths — use `protocol`.
- `hub.get_service("string")` for the owning domain’s service — use `globals.app` (`_with_context` binds from `destination`).
- In `AppService`: proactively `dispatch` Commands — services expose capabilities; they do not own scheduling.

## Hooks (before/after execution)

Register callable hooks on `Hub` for cross-cutting concerns (auth, guardrail, token metering, audit):

```python
hub.before(fn)   # async fn(message) -> Optional[result]; non-None short-circuits
hub.after(fn)    # async fn(message, result=None, exception=None)
```

Before-hooks run in order; after-hooks run in reverse. Can be used as decorators:

```python
@hub.before
async def auth_guard(message):
    if not message.created_by: return {'error': 'unauthorized'}

@hub.after
async def audit_log(message, result=None, exception=None):
    logger.info(f'{message.alias} done')
```

## Parallel dispatch

**yield list/tuple** in async-gen Commands for fan-out/fan-in:

```python
results = yield [TaskA(...), TaskB(...), TaskC(...)]
# results = [resultA, resultB, resultC]
```

Hub detects `list`/`tuple`, dispatches all in parallel, gathers results via `asyncio.gather`, and sends them back.

**hub.gather** for regular (non-generator) Commands:

```python
results = await hub.gather([TaskA(...), TaskB(...)])
```

## Session (global singleton, Protocol KV layer)

`globals.session` = Session **Service** singleton (same pattern as `globals.hub`). Pushed once in `Hub.__init__`, not per-request.

Session is a thin convenience layer over Protocol (default `MemoryProtocol`). Business logic decides what key to use (`trace_id` for conversations, `created_by` for user-scoped data, or any custom key).

| Method | Signature | Purpose |
|--------|-----------|---------|
| `get` | `(key) -> dict` | `protocol.get(key)` |
| `set` | `(key, data: dict)` | `protocol.set(key, data)` |
| `delete` | `(key)` | `protocol.remove(key)` |
| `append` | `(key, field, value)` | `get → dict[field].append(value) → set` |
| `history` | `(key, field, last_n)` | `get → dict[field][-last_n:]` |

Multi-turn conversation (trace_id as key):

```python
class AgentReact(BaseCommand):
    query: str
    async def __call__(self):
        data = await session.get(message.trace_id)
        turns = data.get('turns', [])
        turns.append({'role': 'user', 'content': self.query})
        response = await llm_call(turns, self.query)
        turns.append({'role': 'assistant', 'content': response})
        await session.set(message.trace_id, {**data, 'turns': turns})
        return response
```

User-scoped data (created_by as key):

```python
class CheckQuota(BaseCommand):
    async def __call__(self):
        user = await session.get(message.created_by)
        remaining = user.get('token_quota', 1000)
        if remaining <= 0: return {'error': 'quota exceeded'}
        user['token_quota'] = remaining - used
        await session.set(message.created_by, user)
```

## Introspection (`__str__`)

Every `BaseCommand` / `BaseEvent` instance has a built-in `__str__` for runtime self-description:

```python
str(cmd)  # "Command(OnCacheIngested) dest=timing.AnalysisEngine.OnCacheIngested trace=a1b2c3d4"
str(evt)  # "Event(FibLinesUpdated) dest=timing.AnalysisEngine.FibLinesUpdated trace=a1b2c3d4"
```

Useful in logging, debugging, and any place that needs a human-readable summary of a message instance. The class-level registry output in `Hub.on_started` remains unchanged (uses inline format).

## Handoff (returning Command instance from `__call__`)

When `BaseCommand.__call__` returns another `BaseCommand` instance, `Hub._run` treats it as a **handoff** signal:

1. Inherits `trace_id` from the original message.
2. Merges `data` (`{**original.data, **returned.data}`).
3. Dispatches the returned Command via `hub.dispatch`.
4. Awaits its `state` and forwards the result to the original caller.

The caller sees the final result transparently — as if the original Command produced it.

```python
class RouterAgent(BaseCommand):
    query: str
    async def __call__(self):
        intent = await classify(self.query)
        if intent == 'refund':
            return RefundAgent(query=self.query)      # handoff
        if intent == 'technical':
            return TechSupportAgent(query=self.query)  # handoff
        return await general_reply(self.query)         # normal result
```

Combined with Session for multi-turn handoff:

```python
class AgentA(BaseCommand):
    async def __call__(self):
        await session.append(self.trace_id, 'turns', {'agent': 'A', 'action': 'done'})
        return AgentB(conclusion='needs review')  # handoff, trace_id inherited

class AgentB(BaseCommand):
    conclusion: str
    async def __call__(self):
        history = await session.history(self.trace_id)
        return await deeper_review(self.conclusion, history)
```

> **Note**: chain depth > 5 may degrade performance (stack frames retained). Keep handoff chains shallow.

No new methods or flags needed — `Hub._run` detects `isinstance(result, Message)` (symmetric with `_run_gen`'s `isinstance` checks).

## Trace ID & Future bidirectional link

Every Command's `state` (Future / StreamState) carries `_trace_id`:

```python
cmd = SomeCommand(query='hello')
cmd.state._trace_id == cmd.trace_id  # True
```

Set in `model_post_init` after StreamState replacement, ensuring the final state object always has the correct trace. Useful for correlating Futures back to their originating trace in debugging and distributed tracing.

## globals (important)

- `hub` — Hub Service singleton, pushed once at `__init__`.
- `session` — Session Service singleton, pushed once at `Hub.__init__`. All session ops go through Protocol.
- `app` — resolved from `destination` per-request; cross-domain use `await hub.dispatch(cmd)`.
- `protocol` — from current `app`, per-request.
- `message` — current BaseCommand, per-request.

## Layout & Config

- YAML top-level **domain**, block `app: !module ...`; `commands`, `router_mapping`, `subscribe` all configurable in YAML.
- Unbound Commands go in project root `commands/`.
- `!module`, `protocol.module`, `!env` conventions unchanged.

## CLI

`bollydog ls` lists `TOPIC` (= `destination`). `execute` / `send` / `service` / `shell`.

## UDS entrypoint (optional)

- Env: `BOLLYDOG_UDS_ENABLED=1` registers `UdsService`. `BOLLYDOG_UDS_SOCK_PATH` (server bind). `BOLLYDOG_SEND_DEFAULT_CONFIG` optional default `--config` for `send`.
- Wire: length-prefixed JSON `{"command":"<alias>","kwargs":{}}` → server `resolve` → instance → `hub.dispatch` → `await msg.state`.
- `bollydog send <CommandAlias> <socket_path> ...` — **socket required**; `config` defaults from `BOLLYDOG_SEND_DEFAULT_CONFIG` or pass `--config`. Client: `UdsService(sock_path=socket).send(command, kwargs)`. In-process one-shot remains `execute`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ls` shows no commands | check `--config`; verify `commands` |
| `resolve` fails | alias is case-sensitive (matches class name); use FQN on conflict |
| destination / app unresolved | first two segments must match `Hub.apps` key |
| wrong `app` | always use `globals.app` |

When in doubt, source code + YAML config takes precedence.

## Protocol Taxonomy

Protocols are classified by **data access pattern**, each ABC defines the standard contract:

| ABC | Methods | Use Case | Implementations |
|-----|---------|----------|-----------------|
| `KVProtocol` | `get/set/remove/exists/keys` | Session, cache, state | `MemoryProtocol`, `RedisProtocol`, `SQLiteProtocol`, `CacheLayer` |
| `CRUDProtocol` | `add/add_all/get/list/update/delete/count` | Entity persistence | `SqlAlchemyProtocol`, `PostgreSQLProtocol`, `MySQLProtocol`, `ElasticProtocol`, `DuckDBProtocol` |
| `GraphProtocol` | `execute(query, **params)` | Graph queries | `Neo4jProtocol`, `NeuGProtocol` |
| `FileProtocol` | `read(path)/write(path, data)` | File I/O | `LocalFileProtocol` |

Optional **mixins** (in `_base.py`):

| Mixin | Adds | Applied to |
|-------|------|-----------|
| `BatchMixin` | `update_all/delete_all` | `ElasticProtocol` |
| `StreamMixin` | `stream(**query) -> AsyncIterator` | `ElasticProtocol`, `SqlAlchemyProtocol` |
| `TransactionMixin` | `transaction() -> AsyncContextManager` | `SqlAlchemyProtocol`, `Neo4jProtocol` |
| `DialectMixin` | `compile(stmt) -> (sql, params)` | `SqlAlchemyProtocol`, `DuckDBProtocol` |

### DialectMixin — stmt compilation without engine

Separates SQLAlchemy Layer 2 (dialect compile) from Layer 3 (execution engine). Any Protocol mixing in `DialectMixin` gains `compile(stmt)` which returns `(sql_string, params_dict)` without requiring an engine or connection.

**Two usage modes:**

| Mode | Engine | Dialect source | Example |
|------|--------|----------------|---------|
| Full engine | `create_async_engine(url)` | `engine.dialect` | `SqlAlchemyProtocol`, `PostgreSQLProtocol`, `MySQLProtocol` |
| Native engine | `duckdb.connect()` / custom | `_resolve_dialect(name)` | `DuckDBProtocol` |

```python
# Mode A — SqlAlchemyProtocol: dialect from engine, compile() for logging/debugging
proto = SqlAlchemyProtocol(url='postgresql+asyncpg://...')
sql, params = proto.compile(select(User).where(User.id == 1))

# Mode B — DuckDBProtocol: native engine, compile() for stmt→SQL translation
proto = DuckDBProtocol(url='data/analytics.duckdb')
sql, params = proto.compile(insert(table).values(name='test'), literal_binds=True)
await proto.execute_raw(sql)
```

### Dialect subclasses (all in `sqlalchemy.py`)

```
sqlalchemy.py
  ├─ SQLModelDomain                — ORM base class
  ├─ SqlAlchemyProtocol            — CRUDProtocol + DialectMixin + TransactionMixin + StreamMixin
  │   (Universal SQL: AsyncEngine + Session, URL switches dialect)
  ├─ PostgreSQLProtocol            — SqlAlchemyProtocol subclass
  │   (PG-specific: upsert/ON CONFLICT, pgvector similarity)
  ├─ MySQLProtocol                 — SqlAlchemyProtocol subclass
  │   (MySQL-specific: ON DUPLICATE KEY, INSERT IGNORE, utf8mb4)
  └─ DuckDBProtocol                — CRUDProtocol + DialectMixin
      (Native engine: duckdb.connect + stmt compile + to_thread)
```

Import from `bollydog.adapters`:

```python
from bollydog.adapters import MemoryProtocol, CacheLayer, SQLiteProtocol
from bollydog.adapters import PostgreSQLProtocol, MySQLProtocol, DuckDBProtocol, DialectMixin
from bollydog.adapters import KVProtocol  # for type hints / isinstance checks
```

### Protocol-holds-Protocol (composite pattern)

`Protocol` base class supports `protocol=` parameter — any Protocol can hold an inner Protocol. The inner Protocol's lifecycle is auto-managed via `add_dependency`. This enables composable multi-layer architectures (same pattern as `AppService.protocol`).

```python
Protocol.__init__(self, protocol=None)  # inner protocol, auto add_dependency
```

## CacheLayer — Composite Cache + Persistence

`CacheLayer(KVProtocol)` wraps any `KVProtocol` as its inner `self.protocol`. Memory-first reads, dirty-tracking writes, flush to inner protocol, cold-start recovery.

**Data flow:**

```
Write: set(k,v) → _cache + _dirty → flush() → self.protocol.set()
Read:  get(k)   → _cache hit → return | miss → self.protocol.get() → populate
Lifecycle:
  on_start  → load() from self.protocol → _cache
  on_stop   → flush() remaining dirty keys
  periodic  → compact() delegates to inner protocol
```

**Usage with AppService:**

```python
from bollydog.adapters.composite import CacheLayer
from bollydog.adapters.memory import SQLiteProtocol

class DataEngine(AppService):
    domain = "timing"
    alias = "DataEngine"

    def __init__(self, **kwargs):
        inner = SQLiteProtocol(path='data/klines.db')
        proto = CacheLayer(protocol=inner, flush_threshold=500)
        super().__init__(protocol=proto, **kwargs)
        # inner lifecycle auto-managed — no manual add_dependency needed

    @mode.Service.timer(interval=30.0)
    async def _periodic_flush(self):
        await self.protocol.flush()

    def get_klines(self, symbol, interval):
        return self.protocol._cache.get(f"{symbol}:{interval}", [])

    async def append_bars(self, symbol, interval, bars):
        key = f"{symbol}:{interval}"
        existing = self.protocol._cache.get(key, [])
        existing.extend(bars)
        await self.protocol.set(key, sorted(existing, key=lambda x: x["ts"]))
```

**Multi-layer composition** (Protocol-holds-Protocol nesting):

```python
# L1 memory → L2 Redis → L3 SQLite
l3 = SQLiteProtocol(path='data/persistent.db')
l2 = CacheLayer(protocol=l3, flush_threshold=1000)
l1 = CacheLayer(protocol=l2, flush_threshold=50)
AppService(protocol=l1)  # all three layers lifecycle auto-managed
```

**Backend variants:**

```python
CacheLayer(protocol=SQLiteProtocol(path='data/cache.db'))   # embedded SQL KV
CacheLayer(protocol=RedisProtocol(url='redis://localhost'))  # distributed
CacheLayer(protocol=MemoryProtocol())                        # test / volatile
```

## TableCacheLayer — Columnar Cache + Structured Persistence

`TableCacheLayer(KVProtocol)` wraps a columnar/SQL backend (DuckDB, SQLite, SA) for high-volume structured data. No JSON serialization — uses batch INSERT/SELECT with native types. **10-50x faster cold-start** than CacheLayer for large datasets.

**vs CacheLayer:**

| | CacheLayer | TableCacheLayer |
|--|------------|-----------------|
| Inner protocol | `KVProtocol` (JSON blob) | Any protocol with `adapter.execute(sql)` |
| Serialization | `json.dumps/loads` | None — native SQL types |
| Cold-start 1M rows | 5-15s | 0.3-1s |
| Best for | Small data, any shape | Large structured rows (time-series, logs) |

**Data flow:**

```
Write: set(key, rows) → _cache + _dirty → flush() → DELETE old + batch INSERT
Read:  get(key)        → _cache hit | miss → SELECT WHERE key_columns → populate
Cold:  on_start → SELECT * → group by key_columns → _cache (vectorized, no JSON)
Stop:  flush() remaining dirty keys
```

**Usage:**

```python
from bollydog.adapters.composite import TableCacheLayer
from bollydog.adapters.sqlalchemy import DuckDBProtocol

class DataEngine(AppService):
    domain = "timing"
    alias = "DataEngine"

    _DDL = ('CREATE TABLE IF NOT EXISTS klines ('
            'symbol VARCHAR, "interval" VARCHAR, ts BIGINT, '
            '"open" DOUBLE, high DOUBLE, low DOUBLE, "close" DOUBLE, volume DOUBLE)')

    def __init__(self, db_path="tmp/data.duckdb", **kwargs):
        inner = DuckDBProtocol(url=db_path)
        proto = TableCacheLayer(
            protocol=inner, table='klines', ddl=self._DDL,
            key_columns=['symbol', 'interval'],
            value_columns=['ts', 'open', 'high', 'low', 'close', 'volume'],
            sort_by='ts', flush_threshold=50)
        super().__init__(protocol=proto, **kwargs)

    def get_klines(self, symbol, interval, start_ts=None, end_ts=None):
        rows = self.protocol._cache.get(f"{symbol}:{interval}", [])
        if start_ts: rows = [x for x in rows if x["ts"] >= start_ts]
        if end_ts: rows = [x for x in rows if x["ts"] <= end_ts]
        return rows

    async def append_bars(self, symbol, interval, bars):
        key = f"{symbol}:{interval}"
        existing = self.protocol._cache.get(key, [])
        existing.extend(bars)
        await self.protocol.set(key, sorted(existing, key=lambda x: x["ts"]))
```

**compound_key format**: `"val1:val2"` matching `key_columns` order (e.g. `"BTCUSDT:1h"` for `['symbol', 'interval']`).
