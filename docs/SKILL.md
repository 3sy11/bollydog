---
name: bollydog-framework
description: bollydog framework quick-ref — architecture, patterns, configuration, protocols, and best practices.
---

# Bollydog Framework Guide

Async microservice framework built on `mode`. Commands as executable units, Hub as central dispatcher, Protocols as pluggable data layers.

## Architecture Overview

```
CLI / HTTP / WS / UDS
        │
   load_from_config(toml)
        │
   ┌────▼────┐
   │   Hub   │── Exchange (pub/sub router)
   │         │── Session  (KV via Protocol)
   │         │── Queue    (qos=1 buffer)
   └────┬────┘
        │  dispatch / execute
   ┌────▼──────────┐
   │  AppService   │── protocol (data layer)
   │  (domain)     │── commands (ClassVar)
   │               │── router_mapping / subscriber
   └───────────────┘
```

**Key types**: `BaseCommand` (callable action), `BaseEvent` (fire-and-forget), `AppService` (resource owner), `Protocol` (data access), `Hub` (dispatcher + lifecycle).

## Quick Start

```python
# myapp/app.py
from bollydog.models.service import AppService

class MyService(AppService):
    domain = 'myapp'
    commands = ['commands']
```

```python
# myapp/commands.py
from bollydog.models.base import BaseCommand

class Hello(BaseCommand):
    name: str = 'world'
    async def __call__(self):
        return {'hello': self.name}
```

```toml
# config.toml
["myapp.app.MyService"]
commands = ["commands"]
```

```bash
bollydog ls --config config.toml
bollydog execute Hello --config config.toml --name bollydog
```

## Dispatch Pipeline

`Hub.dispatch(message)` routes by type and qos:

| Path | Condition | Routing | Publish |
|------|-----------|---------|---------|
| Event | `BaseEvent` | `create_task(_fire)` | Yes |
| Command qos=0 | default | `create_task(_fire)` | Yes |
| Command qos=1 | `qos=1` | `queue.put` -> consumer | Yes |

All paths go through `_execute(msg, runner)` which runs before-hooks -> runner -> after-hooks.

- **`_run`**: coroutine runner with retry. Detects handoff (return Command instance).
- **`_run_gen`**: async generator runner. Detects `yield Command` (sequential), `yield [cmd, ...]` (parallel fan-out/fan-in), `yield value` (stream).
- **`_with_context`**: pushes `app`, `protocol`, `message` globals per request scope.
- **`_publish`**: matches `destination` topic via Exchange, dispatches handler Commands.
- **`execute`**: CLI direct mode. No queue, no publish.

## Command Patterns

### 1. Pure compute — no globals needed, unit-testable in isolation

```python
class Compute(BaseCommand):
    data: list
    async def __call__(self):
        return sum(self.data)
```

### 2. Orchestration — uses `app` methods + `protocol` persistence

```python
class ProcessData(BaseCommand):
    async def __call__(self):
        result = app.transform(self.data)       # business method on AppService
        await protocol.set('result', result)     # persistence via protocol
        await hub.emit(DataReady(key='result'))  # emit event
        return result
```

### 3. Async generator — yield sub-commands, parallel fan-out

```python
class Pipeline(BaseCommand):
    async def __call__(self):
        a = yield StepA()                              # sequential
        results = yield [TaskB(), TaskC(), TaskD()]     # parallel
        yield {'a': a, 'parallel': results}             # stream value
```

### 4. Handoff — return Command instance to delegate

```python
class Router(BaseCommand):
    query: str
    async def __call__(self):
        intent = classify(self.query)
        if intent == 'refund': return RefundAgent(query=self.query)  # handoff
        return await general_reply(self.query)                        # normal
```

Handoff inherits `trace_id`, merges `data`, dispatches transparently. Keep chains shallow (depth > 5 may degrade perf).

## Globals (request-scoped)

| Name | Type | Scope | Description |
|------|------|-------|-------------|
| `hub` | Hub | singleton | Central dispatcher |
| `session` | Session | singleton | KV session via Protocol |
| `app` | AppService | per-request | Resolved from `destination` |
| `protocol` | Protocol | per-request | From current `app.protocol` |
| `message` | BaseCommand | per-request | Current executing command |

```python
from bollydog.globals import hub, app, protocol, session, message
```

## Destination & Topic

Format: `domain.ServiceAlias.CommandAlias` (3-part topic).

- Unbound commands default to `_._.CommandAlias`; `_load_commands` rewrites to `{domain}.{alias}.{CommandAlias}`.
- `AppService.resolve_app(msg)` takes first two segments to find the owning service.
- Exchange uses full destination as topic for pattern matching.

## Exchange (pub/sub)

```python
# In AppService class or TOML subscriber config
subscriber = {'analytics.*.DataReady': OnDataReady}
```

- AMQP-style wildcards: `*` = one segment, `#` = zero or more.
- Handlers must be **Command classes** (not instances).
- `_publish` fires matched handlers with `add_event(original_msg)`.

## Hooks (before/after)

```python
@hub.before
async def auth_guard(message):
    if not message.created_by: return {'error': 'unauthorized'}  # short-circuit

@hub.after
async def audit(message, result=None, exception=None):
    logger.info(f'{message.alias} done')
```

Before-hooks run in order; after-hooks in reverse. Non-None return from before short-circuits execution.

## Session

Global singleton (`globals.session`). Thin KV layer over Protocol (default `MemoryProtocol`).

```python
await session.get(key)                   # -> dict
await session.set(key, data)
await session.append(key, 'turns', msg)  # list append
turns = await session.history(key)       # -> list
```

Business logic chooses the key: `trace_id` for conversations, `created_by` for user scope, etc.

## AppService Design

```python
class DataEngine(AppService):
    domain = 'trading'
    commands = ['commands']
    subscriber = {'trading.*.BarsReady': OnBarsReady}

    def transform(self, data):
        return processed_data  # business method called by Commands
```

Key rules:
- `protocol` is auto-assigned when `add_dependency` receives a `Protocol` instance.
- `_apps` ClassVar is the global service registry; `__init__` auto-registers.
- `create_from(**conf)` merges TOML config into ClassVar (`commands`, `router_mapping`, `subscriber`).
- Commands access the owning service via `globals.app`; never reach into sub-services.

## Protocol System

### Base class

`Protocol(BaseService)` — lifecycle managed by `mode.Service`. Subclasses implement `on_start` (init adapter), `on_stop` (cleanup), `__aenter__`/`__aexit__` (connection scope).

### ABC hierarchy

| ABC | Methods | Use Case |
|-----|---------|----------|
| `KVProtocol` | `get/set/remove/exists/keys` | Session, cache, state |
| `CRUDProtocol` | `add/add_all/get/list/update/delete/count` | SQL, Elasticsearch |
| `GraphProtocol` | `execute(query, **params)` | Neo4j, GraphScope |
| `FileProtocol` | `read/write` | File I/O, TOML config |

### Implementations

```
memory.py     MemoryProtocol, RedisProtocol, SQLiteProtocol
sqlalchemy.py SqlAlchemyProtocol, PostgreSQLProtocol, MySQLProtocol, DuckDBProtocol
graph.py      Neo4jProtocol, NeuGProtocol
file.py       LocalFileProtocol, TOMLFileProtocol
elastic.py    ElasticProtocol
composite.py  CacheLayer, TableCacheLayer
```

Import specific modules to avoid pulling optional dependencies:

```python
from bollydog.adapters.memory import SQLiteProtocol
from bollydog.adapters.composite import CacheLayer
```

### Mixins

| Mixin | Adds | Used by |
|-------|------|---------|
| `BatchMixin` | `update_all/delete_all` | ElasticProtocol |
| `StreamMixin` | `stream() -> AsyncIterator` | SqlAlchemy, Elastic |
| `TransactionMixin` | `transaction() -> ctx` | SqlAlchemy, Neo4j |
| `DialectMixin` | `compile(stmt) -> (sql, params)` | SqlAlchemy, DuckDB |

### Composite Protocol (decorator pattern)

Protocol-holds-Protocol via `add_dependency`. Inner protocol lifecycle is auto-managed.

**CacheLayer** — memory cache + KV persistence backend:

```python
inner = SQLiteProtocol(path='data/state.db')
proto = CacheLayer(flush_threshold=200)
proto.add_dependency(inner)  # or via TOML nesting
# Flow: set -> cache + dirty -> flush -> inner.set
# Cold start: on_started -> load all from inner
```

**TableCacheLayer** — memory cache + columnar table backend (DuckDB/SQLite). No JSON serialization, native SQL types, 10-50x faster cold-start for large datasets.

```python
inner = DuckDBProtocol(url='data/analytics.duckdb')
proto = TableCacheLayer(table='klines', key_columns=['symbol', 'interval'],
    value_columns=['ts', 'open', 'high', 'low', 'close', 'volume'],
    sort_by='ts', flush_threshold=50)
proto.add_dependency(inner)
```

**Multi-layer nesting**:

```python
# L1 memory -> L2 Redis -> L3 SQLite (all lifecycle auto-managed)
l3 = SQLiteProtocol(path='data/persistent.db')
l2 = CacheLayer(flush_threshold=1000); l2.add_dependency(l3)
l1 = CacheLayer(flush_threshold=50);   l1.add_dependency(l2)
svc.add_dependency(l1)
```

### DialectMixin — compile without engine

Separates SQLAlchemy dialect compilation from execution engine:

```python
# SqlAlchemyProtocol: dialect from engine
sql, params = proto.compile(select(User).where(User.id == 1))

# DuckDBProtocol: native engine, compile for stmt->SQL translation
sql, params = proto.compile(insert(table).values(name='test'), literal_binds=True)
await proto.execute_raw(sql)
```

## TOML Configuration

### Structure

```toml
["myapp.app.MyService"]
commands = ["commands", "extra_commands"]

["myapp.app.MyService".router_mapping]
Ping = ["GET",  "/api/ping"]
Echo = ["POST", "/api/echo"]
Stream = ["SSE", "/api/stream"]

["myapp.app.MyService".subscriber]
"analytics.*.DataReady" = "myapp.commands.OnDataReady"

["myapp.app.MyService".protocol]
module = "bollydog.adapters.composite.CacheLayer"
flush_threshold = 500

["myapp.app.MyService".protocol.protocol]
module = "bollydog.adapters.memory.SQLiteProtocol"
path = "data/state.db"
```

Top-level key = fully-qualified AppService class. `module` key in protocol sections = import path. Nested `protocol` sub-tables build the protocol chain recursively.

| Config Key | Type | Merged Into |
|------------|------|-------------|
| `commands` | `list[str]` | `cls.commands` ClassVar |
| `router_mapping` | `dict` | `cls.router_mapping` ClassVar |
| `subscriber` | `dict` | `cls.subscriber` ClassVar |
| `protocol` | `dict` | Instance `protocol` via `add_dependency` |
| `depends` | `list[str]` | Resolved after all services created |
| other keys | any | Passed as `**kwargs` to `__init__` |

### Service lifecycle

```
load_from_config(config)
  1. Parse TOML -> cls.create_from(**conf) per section
  2. Create entrypoint services (HTTP/WS/UDS if enabled)
  3. Resolve depends -> add_dependency
  4. _load_commands per service class (deferred, once)

Hub()
  on_init_dependencies -> Exchange, Session, Queue
  on_first_start       -> push globals (hub, session)
  on_start             -> _load_commands for Hub
  on_started           -> maybe_start all AppService._apps
```

## CLI

```bash
bollydog service --config config.toml [--domains myapp,infra]
bollydog ls --config config.toml
bollydog execute <Command> --config config.toml [--param value]
bollydog shell --config config.toml
bollydog send <Command> <socket_path> [--config ...]
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BOLLYDOG_COMMAND_EXPIRE_TIME` | `3600` | Command timeout (s) |
| `BOLLYDOG_DEFAULT_QOS` | `1` | Default QoS level |
| `BOLLYDOG_QUEUE_MAX_SIZE` | `1000` | qos=1 queue capacity |
| `BOLLYDOG_HTTP_ENABLED` | `0` | Enable HTTP entrypoint |
| `BOLLYDOG_WS_ENABLED` | `0` | Enable WebSocket entrypoint |
| `BOLLYDOG_UDS_ENABLED` | `0` | Enable UDS entrypoint |

## Design Rules

1. **Command** = thin orchestration/glue. No owned state. Access `app` methods, `protocol` for persistence.
2. **AppService** = resource owner. Expose business methods. Inner sub-services stay invisible to Commands.
3. **Protocol** = environment abstraction. Swap `SqlAlchemyProtocol` -> `MemoryProtocol` for tests.
4. Use `globals.app` (bound by `_with_context` from `destination`). Never `app.child_service.xxx`.
5. Cross-domain: `hub.dispatch(cmd)` or `yield cmd`. Never grab foreign services directly.
6. AppService does not proactively dispatch Commands — it exposes capabilities, Commands schedule.

## Testing Strategy

| Layer | Production | Test |
|-------|------------|------|
| Protocol | `SqlAlchemy`, `Redis` | `MemoryProtocol`, `NoneProtocol` |
| AppService methods | real impl | mock return values |
| Pure compute Command | `await cmd()` | same, no Hub needed |
| Orchestration Command | full Hub | mock `app.method` + `MemoryProtocol` |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ls` shows no commands | Check `--config`; verify `commands` list |
| `resolve` fails | Alias is case-sensitive; use FQN on conflict |
| Wrong `app` in Command | Ensure `destination` matches service key |
| Protocol not started | Must be added via `add_dependency`, not just assigned |
