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
   ┌────▼─────────┐
   │  Bootstrap   │── mode.Worker, unified entry for service/execute
   │  (Worker)    │── pushes registry/hub/session/services globals
   └────┬─────────┘
        │
   ┌────▼──────────┐          ┌───────────────┐
   │  Registry     │          │   Exchange    │
   │  Service      │          │               │
   │ {destination  │          │ {topic →      │
   │  → CommandCls}│          │  [EventCls]}  │
   └────┬──────────┘          └───────┬───────┘
        │                             │
   ┌────▼─────────────────────────────▼────┐
   │   Hub   dispatch / execute / emit     │
   │         Session (KV via Protocol)     │
   │         Queue   (message buffer)      │
   └────┬──────────────────────────────────┘
        │
   ┌────▼──────────┐
   │  AppService   │── protocol (data layer)
   │  (domain)     │── commands / subscribe (config)
   └───────────────┘
```

**Key types**: `BaseCommand` (callable action), `BaseEvent` (a Command subclass nobody awaits), `AppService` (resource owner), `Protocol` (data access), `HubService` (dispatcher + lifecycle), `RegistryService` (destination → Command index), `Exchange` (topic → Event class index), `Bootstrap` (unified Worker entry), `ExecuteService` (lightweight one-shot executor).

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

### Two execution modes

| Mode | Entry | Runner | Queue | Exchange | Use Case |
|------|-------|--------|-------|----------|----------|
| **service** | `Bootstrap(hub)` | `HubService` | Yes | Yes | Long-running daemon, full pub/sub |
| **execute** | `Bootstrap(executor)` | `ExecuteService` | No | No | One-shot CLI command execution |

### CommandRunnerMixin (shared logic)

Both `HubService` and `ExecuteService` extend `CommandRunnerMixin`. Subclass must implement `_submit(message) -> Any` to route sub-commands (Queue pipeline vs inline recursive).

`_execute(msg, runner)` runs before-hooks -> runner -> after-hooks.

- **`_run`**: coroutine runner with retry. Detects handoff (return Command instance).
- **`_run_gen`**: async generator runner. Detects `yield Command` (sequential), `yield [cmd, ...]` (parallel fan-out/fan-in), `yield value` (stream).
- **`_with_context`**: asynccontextmanager, pushes `app`, `protocol`, `message` globals per request scope.
- **`_run_with_context`**: combines `_with_context` + `_execute`, convenience method.

### HubService (service mode)

`Hub.dispatch(message)` — unified Queue path:

All messages (Command + Event) go through `queue.put()` -> consumer `queue.take()` -> `create_task(_process_and_complete)`.
`execute(msg)` = `dispatch(msg)` + `await msg.state` (syntactic sugar).
`emit(topic)` = `exchange.instantiate(topic)` + `dispatch` each, without awaiting any of them.

Hub accesses Exchange and Queue lazily via `apps` proxy (not via `on_init_dependencies`).

### ExecuteService (execute mode)

Lightweight one-shot executor — no Queue, no Exchange, no consumer loop.

`execute(message)` directly calls `_with_context` + `_execute`. Sub-commands (`_submit`) are executed inline recursively. Target AppService + Protocol are started on demand (`maybe_start`).

## Command Patterns

### Command Signature Convention

A Command is a Pydantic model — its **input parameters** are the fields defined on the subclass (excluding all `_ModelMixin` and `BaseCommand` base fields), and its **return type** is the `__call__` return annotation.

**Signature format**: `CommandName(field1: type, field2: type, ...) → ReturnType`

```python
class PushBars(BaseCommand):
    symbol: str = ""
    interval: str = ""
    bars: list[dict] = Field(default_factory=list)
    replay: bool = False
    async def __call__(self) -> dict: ...
```

Signature: `PushBars(symbol: str, interval: str, bars: list[dict], replay: bool) → dict`

**Constraints**:

- **Input fields** must be primitive types only: `str`, `int`, `float`, `bool`, `list`, `dict`. No class references or complex objects.
- **Return type** must be primitive types only: `str`, `int`, `float`, `bool`, `list`, `dict`, `None`, or unions thereof (e.g. `dict | None`). Never return domain model classes, Protocol objects, or any non-serializable reference.
- `__call__` must explicitly annotate its return type. `-> Any` is forbidden in final implementations.

This convention applies to all documentation (sequence diagrams, interface contracts) and runtime introspection (`__str__` output).

### 1. Pure compute — no globals needed, unit-testable in isolation

```python
class Compute(BaseCommand):
    data: list
    async def __call__(self) -> float:
        return sum(self.data)
```

### 2. Orchestration — uses `app` methods + `protocol` persistence

```python
class ProcessData(BaseCommand):
    key: str
    async def __call__(self) -> dict:
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
    async def __call__(self) -> dict:
        intent = classify(self.query)
        if intent == 'refund': return RefundAgent(query=self.query)  # handoff
        return await general_reply(self.query)                        # normal
```

Handoff inherits `trace_id`, merges `data`, dispatches transparently. Keep chains shallow (depth > 5 may degrade perf).

## Globals (request-scoped)

| Name | Type | Scope | Description |
|------|------|-------|-------------|
| `hub` | HubService | singleton | Central dispatcher |
| `session` | Session | singleton | KV session via Protocol |
| `registry` | RegistryService | singleton | Centralized command/event binding and subscription index |
| `services` | MutableMappingProxy | singleton | Service registry (`{domain.alias: svc}`) |
| `app` | AppService | per-request | Resolved from `destination` |
| `protocol` | Protocol | per-request | From current `app.protocol` |
| `message` | BaseCommand | per-request | Current executing command |

```python
from bollydog.globals import hub, app, services, registry, protocol, session, message
```

`services` is a `MutableMappingProxy` over `LocalStack` — forwards dict operations (`__getitem__`, `get`, `values`, etc.) to the underlying service registry dict pushed by Bootstrap.

`registry` is a `Proxy` over `LocalStack` — pushed during `Bootstrap.__init__`, provides `all_commands`, `add_command`, `resolve`, `resolve_app`, `get_app`. Events are not in it; they live in Exchange, reached through `hub.emit` or `services.exchange`.

## Destination & Topic

Format: `domain.ServiceAlias.CommandAlias` (3-part topic).

- Commands without explicit `destination` are bound via dynamic subclass at registration time: `type(Name, (OriginalCls,), {'destination': dest})`. Original class stays unchanged.
- `registry.resolve_app(msg)` reads `type(msg).destination` and takes first two segments to find the owning service from `services`.
- An Event's destination doubles as its default topic in Exchange.

## Exchange (pub/sub)

An Event is just a Command subclass that nobody awaits. It carries its own reaction logic in `__call__(self)` and rides the same Queue pipeline as any Command, reaching `app` / `protocol` / `message` through the usual context proxies. There is no separate handler abstraction and no dynamically generated wrapper class.

Exchange holds two indexes and nothing else:

- `_events`: topic (exact destination or wildcard pattern) → list of Event classes
- `_classes`: destination → Event class, for exact lookup

Every Event found while scanning a service's `commands` modules is registered under its own destination. `subscribe` then aliases those same classes onto extra topics — values are **Event class names**, not method names.

```python
# trading/commands.py
class BarsReady(BaseEvent):
    """Notification only — no __call__ needed."""

class OnDataReady(BaseEvent):
    async def __call__(self):
        source = self.data['events'][-1]
        await app.recompute(source['data'])

class UpdateCache(BaseEvent):
    async def __call__(self): ...
```

```toml
["trading.DataEngine"]
module = "trading.app.DataEngine"
commands = ["commands"]
subscribe = { "analytics.*.DataReady" = "OnDataReady", "trading.DataEngine.BarsReady" = ["OnDataReady", "UpdateCache"] }
```

A short name is resolved against the declaring service (`f'{key}.{name}'`); a dotted name is taken as a full destination. An unresolvable name fails the build with a clear error rather than silently doing nothing.

### Publishing

```python
await hub.emit(topic='trading.DataEngine.BarsReady', source=message)  # fan out by topic
await hub.emit(event=BarsReady(data={'sym': 'AAPL'}))                 # dispatch one instance
await hub.emit(source=message)                                        # topic defaults to message.destination
```

`emit` matches the topic, instantiates every bound Event class, appends `source.model_dump()` to each instance's `data['events']` list, and dispatches them all through the Queue. It returns the instances without awaiting them — a publisher never blocks on its subscribers.

- AMQP-style wildcards: `*` = one segment, `#` = zero or more.
- Fan-out is resolved in one pass at emit time; there is no "event completes, then subscribers fire" second stage.
- Runtime binding via `exchange.add_event(topic, cls)` / `exchange.remove_event(topic, cls)`.

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
await session.get(key)                            # -> dict
await session.set(key, data)
await session.delete(key)                         # remove key
await session.append(key, 'turns', msg)           # list append to field
turns = await session.history(key)                # -> list (field='turns')
turns = await session.history(key, field='msgs', last_n=10)  # last N items
```

Business logic chooses the key: `trace_id` for conversations, `created_by` for user scope, etc.

## AppService Design

```python
class DataEngine(AppService):
    domain = 'trading'
    commands = ['commands']
    depends = ['infra.ConfigEngine']                    # resolved to instances at startup
    subscribe = {'trading.*.BarsReady': 'OnBarsReady'}  # Event class name, not method name

    def transform(self, data):
        return processed_data  # business method called by Commands and Events
```

Key rules:
- `protocol` is auto-assigned when `add_dependency` receives a `Protocol` instance.
- Service registry is the `services` MutableMappingProxy (`globals.services`), keyed by `{domain}.{alias}`. Populated by Bootstrap.
- `RegistryService` holds command bindings; `Exchange` holds event topics. Reached via `globals.registry` and `services.exchange`.
- `create_from(**conf)` merges TOML config (`commands`, `routers`, `subscribe`, `depends`) with class-level defaults.
- `registry.resolve_app(message)` reads `type(msg).destination` and uses first two segments to find the owning service from `services`.
- Commands access the owning service via `globals.app`; never reach into sub-services.

## Protocol System

### Base class

`Protocol(BaseService)` — lifecycle managed by `mode.Service`. Base class sets `domain = "adapters"`. Subclasses implement `on_start` (init adapter), `on_stop` (cleanup), `__aenter__`/`__aexit__` (connection scope).

Protocol uses `__aenter__`/`__aexit__` for connection-scope management, separate from `mode.Service`'s lifecycle (`on_start`/`on_stop`). This allows short-lived connection contexts (e.g., DuckDB queries) within a long-lived service.

### Adapter Convention

Adapter parameters are declared as **class attributes with defaults**, not `__init__` parameters. Only connection-type parameters (URLs, auth) may use `os.getenv` fallbacks:

```python
class RedisProtocol(KVProtocol):
    url: str = os.getenv('REDIS_URL', 'redis://localhost')  # connection: env var fallback
    def __init__(self, **kwargs):
        super().__init__(**kwargs)                            # no param signature

class DuckDBProtocol(CRUDProtocol, DialectMixin):
    url: str = ':memory:'     # non-connection: plain default
    metadata: MetaData = None
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### ABC hierarchy

| ABC | Methods | Use Case |
|-----|---------|----------|
| `KVProtocol` | `get/set/remove/exists/keys` | Session, cache, state |
| `CRUDProtocol` | `add/add_all/get/list/update/delete/count` | SQL, DuckDB |
| `GraphProtocol` | `execute(query, **params)` | Neo4j, GraphScope |
| `FileProtocol` | `read/write` | File I/O, TOML config |

### Implementations

```
memory.py     MemoryProtocol, RedisProtocol, SQLiteProtocol
sqlalchemy.py SqlAlchemyProtocol, PostgreSQLProtocol, MySQLProtocol, DuckDBProtocol
graph.py      Neo4jProtocol, NeuGProtocol
file.py       LocalFileProtocol, TOMLFileProtocol
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
| `BatchMixin` | `update_all/delete_all` | SqlAlchemy, DuckDB |
| `StreamMixin` | `stream() -> AsyncIterator` | SqlAlchemy, DuckDB |
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

### Unified `domain.alias` Key Model

All TOML keys use `domain.alias` format as the unique reference key. Every entry must have an explicit `module` field. Protocols use `domain = "adapters"`.

```toml
# ── Framework services (bollydog/service/config.toml) ──
["adapters.MemoryProtocol"]
module = "bollydog.adapters.memory.MemoryProtocol"

["bollydog.Session"]
module = "bollydog.service.session.Session"
protocol = "adapters.MemoryProtocol"

["bollydog.HubService"]
module = "bollydog.service.app.HubService"
commands = ["commands"]
depends = ["bollydog.RegistryService", "bollydog.Exchange",
           "bollydog.Queue", "bollydog.Session"]

# ── Application services (app.toml) ──
["adapters.duckdb_wh"]
module = "bollydog.adapters.sqlalchemy.DuckDBProtocol"
url = "data/warehouse.duckdb"

["trading.DataEngine"]
module = "trading.app.DataEngine"
protocol = "adapters.duckdb_wh"
depends = ["bollydog.Session"]
commands = ["commands"]

["trading.DataEngine".routers]
Ping = ["GET",  "/api/ping"]
```

`subscribe` is an inline table, so it stays on the service's own key rather than opening a sub-table:

```toml
["trading.DataEngine"]
subscribe = { "analytics.*.DataReady" = "OnDataReady" }
```

### Reference System

All references (`depends`, `protocol`) use `domain.alias` strings that resolve against the same flat config dict:

| Reference | Format | Example |
|-----------|--------|---------|
| TOML key | `domain.alias` | `["trading.DataEngine"]` |
| `protocol` | `domain.alias` string | `protocol = "adapters.duckdb_wh"` |
| `depends` | list of `domain.alias` | `depends = ["bollydog.Session"]` |
| `services` dict key | `domain.alias` | `services["trading.DataEngine"]` |

### Config Keys

| Config Key | Type | Handling |
|------------|------|----------|
| `module` | `str` | Import path. Popped by Bootstrap before `create_from` |
| `commands` | `list[str]` | Merged with ClassVar default by `AppService.create_from` |
| `routers` | `dict` | Merged with ClassVar default by `AppService.create_from` |
| `subscribe` | `dict` | Merged with ClassVar default by `AppService.create_from`; values are Event class names |
| `depends` | `list[str]` | Stored as `_depends`, resolved to `dict` in Phase 2 |
| `protocol` | `str` | Stored as `_protocol`, bound in Phase 2 via `add_dependency` |
| other keys | any | Injected via `setattr` onto instance |

### Attribute Injection

All remaining TOML parameters (after framework keys are popped) are injected via `setattr` onto the service instance. This means:

- Service/Protocol classes declare configurable parameters as **class attributes with defaults**.
- TOML overrides only non-default values.
- No explicit `__init__` parameter signatures for configurable fields.

```python
class DuckDBProtocol(CRUDProtocol, DialectMixin):
    url: str = ':memory:'           # class attr, overridden by TOML
    metadata: MetaData = None

    def __init__(self, **kwargs):   # no url/metadata params
        super().__init__(**kwargs)
```

```toml
["adapters.duckdb_wh"]
module = "bollydog.adapters.sqlalchemy.DuckDBProtocol"
url = "data/warehouse.duckdb"      # overrides class default via setattr
```

### Parameter Principle

TOML should be minimal. If a parameter equals its class default, omit it from TOML.

### Service lifecycle

Bootstrap loads multiple TOML sources and builds all services in a 2-phase pipeline:

```
Bootstrap(mode.Worker)
  __init__(config=path)
    -> config (cached_property): merge framework TOML + entrypoint TOMLs + app TOML
    -> _build_services(): 2-phase pipeline
       Phase 1: for each TOML entry: pop module, smart_import, cls.create_from(**conf),
                setattr alias/domain from key
       Phase 2: one pass per instance, four independent wirings —
                  _protocol reference   -> add_dependency
                  _depends list         -> instance.depends dict via add_dependency
                  _walk_modules scan    -> Commands to Registry, Events to Exchange
                  subscribe entries     -> alias registered Event classes onto extra topics
       -> returns flat dict {domain.alias: instance}
    -> filter AppService instances into BollydogServices (typed dict)
    -> push all context stacks unconditionally: services, registry, session, hub

  on_first_start -> install signals
  on_started
    -> execute mode: executor.execute(msg) -> stop
    -> service mode: maybe_start all, log bindings
  on_shutdown -> services.clear()

HubService(CommandRunnerMixin, AppService)
  exchange/queue -> lazy @property, resolved from services dict
```

### create_from Hierarchy

```
BaseService.create_from     → cls() + setattr (pure injection, no protocol/depends)
  ↑
Protocol.create_from        → pop protocol → _protocol, then super()
  ↑
AppService.create_from      → pop commands/routers/subscribe/protocol/depends,
                              merge ClassVar defaults, then super()
```

## CLI

```bash
bollydog service --config config.toml [--domains myapp,infra]
bollydog ls --config config.toml
bollydog execute <Command> --config config.toml [--timeout 300] [--param value]
bollydog shell --config config.toml
bollydog send <Command> <socket_path> [--config ...]
```

### Command resolution

CLI uses `registry.resolve(command)` for exact destination matching. Raises `KeyError` if not found.

### `service` vs `execute` mode

- `service`: `Bootstrap(config=path).run()` — daemon, full lifecycle.
- `execute`: `Bootstrap(config=path).run(msg, timeout)` — one-shot, stops after completion. `timeout` parameter is unified into `message.expire_time`.

## Environment Variables

Environment variables are minimal — most configuration lives in TOML and class attributes.

### Command (models/base.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `COMMAND_EXPIRE_TIME` | `3600` | Command timeout (s) |
| `COMMAND_DEFAULT_SIGN` | `1` | Soft-delete marker (1=normal, -1=deleted) |
| `COMMAND_DELIVERY_COUNT` | `0` | Retry count on timeout |

### Entrypoint Toggle (bollydog/config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENTRYPOINT_HTTP_ENABLED` | `0` | Enable HTTP entrypoint |
| `ENTRYPOINT_WS_ENABLED` | `0` | Enable WebSocket entrypoint |
| `ENTRYPOINT_UDS_ENABLED` | `0` | Enable UDS entrypoint |

### Adapter Connection (class attributes with env var fallback)

| Variable | Default | Used by |
|----------|---------|---------|
| `REDIS_URL` | `redis://localhost` | `RedisProtocol.url` |
| `NEO4J_URL` | `bolt://localhost:7687` | `Neo4jProtocol.url` |

All other service/protocol parameters are configured via TOML or class attribute defaults — no env vars.

### Entrypoint Parameters

HTTP, WebSocket, and UDS service parameters (host, port, debug, log_level, etc.) are now **class attributes** on the respective service classes, configurable via TOML injection. No individual env vars.

## Design Rules

1. **Command** = thin orchestration/glue. No owned state. Access `app` methods, `protocol` for persistence.
2. **AppService** = resource owner. Expose business methods. Inner sub-services stay invisible to Commands.
3. **Protocol** = environment abstraction. Swap `SqlAlchemyProtocol` -> `MemoryProtocol` for tests.
4. Use `globals.app` (bound by `_with_context` from `destination`). Never `app.child_service.xxx`.
5. **Cross-domain access**: undeclared services must go through `hub.dispatch(cmd)` or `yield cmd`. **Declared dependencies** (via `depends` in TOML/class) can be accessed directly via `self.get_dependency("domain.alias").method(...)` — the dependency is explicit, lifecycle-managed, and auditable.
6. AppService does not proactively dispatch Commands — it exposes capabilities, Commands schedule.
7. **Command fields and return values must be primitive types** (`str`, `int`, `float`, `bool`, `list`, `dict`, `None`). No class references, domain model instances, or complex objects as input fields or return values. This ensures Commands are naturally serializable, transportable across process boundaries, and self-describing for service discovery.

## Testing Strategy

### Four-layer test model

| Layer | What to test | Tools | Hub needed? |
|-------|-------------|-------|-------------|
| 1. Pure logic | `match_topic`, `__init_subclass__` | `def test_*()` — sync, no fixture | No |
| 2. Protocol standalone | `MemoryProtocol`, `SQLiteProtocol`, `CacheLayer` | `async with proto:` (lazy `maybe_start`) | No |
| 3. Command unit | Single Command `__call__` with context | `run_command(cmd, app, protocol)` | No |
| 4. E2E integration | Full dispatch → Queue → run → result | `run_hub()` context manager or `hub` fixture | Yes |

### Test utilities (`bollydog/testing.py`)

```python
from bollydog.testing import command_context, run_command, run_hub, run_execute

# Layer 3: Command unit test
with command_context(app=my_app, protocol=my_proto):
    result = await cmd()

result = await run_command(cmd, app=my_app, protocol=my_proto)

# Layer 4: E2E test (full Hub + Queue + Exchange)
async with run_hub('config.toml') as hub:
    result = await hub.execute(MyCommand(x=1))

# Layer 4 alternative: lightweight E2E (ExecuteService, no Queue/Exchange)
async with run_execute('config.toml') as executor:
    result = await executor.execute(MyCommand(x=1))
```

### Fixtures (`tests/conftest.py`)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `clean_globals` | autouse | Clears all `LocalStack` (services, registry, hub, session, etc.) after each test |
| `memory_protocol` | per-test | Standalone `MemoryProtocol` with lifecycle |
| `hub` | per-test | Full Hub via `run_hub()`, loads `bollydog/service/config.toml` |

### Production / test swap

| Layer | Production | Test |
|-------|------------|------|
| Protocol | `SqlAlchemy`, `Redis` | `MemoryProtocol` |
| AppService methods | real impl | mock return values |
| Pure compute Command | `await cmd()` | same, no Hub needed |
| Orchestration Command | full Hub | mock `app.method` + `MemoryProtocol` |

### Running tests

```bash
uv run pytest                         # all tests + coverage
uv run pytest -m unit                 # unit only
uv run pytest -m "not slow"           # skip slow
uv run pytest tests/test_protocol.py  # single file
```

Coverage reports: `tmp/htmlcov/` (HTML), `tmp/coverage.xml` (XML).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ls` shows no commands | Check `--config`; verify `commands` list in TOML/class |
| `resolve` fails | Use full destination; suffix match only works in CLI |
| Wrong `app` in Command | Ensure class-level `destination` matches service key |
| Protocol not started | Must be added via `add_dependency`, not just assigned |
| subscriber not triggered | Verify `subscribe` config in TOML; check `services.exchange.all_events()` |
