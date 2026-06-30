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
   ┌────▼──────────┐
   │  Registry     │── commands: {destination → BoundCommandClass}
   │  Service      │── subscribers: {topic → Set[destination]}
   └────┬──────────┘
        │
   ┌────▼────┐
   │   Hub   │── Exchange (stateless event trigger, reads registry)
   │         │── Session  (KV via Protocol)
   │         │── Queue    (message buffer)
   └────┬────┘
        │  dispatch / execute
   ┌────▼──────────┐
   │  AppService   │── protocol (data layer)
   │  (domain)     │── commands / subscribers (config)
   └───────────────┘
```

**Key types**: `BaseCommand` (callable action), `BaseEvent` (fire-and-forget), `AppService` (resource owner), `Protocol` (data access), `HubService` (dispatcher + lifecycle), `RegistryService` (centralized binding/subscription index), `Exchange` (stateless event routing trigger), `Bootstrap` (unified Worker entry), `ExecuteService` (lightweight one-shot executor).

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

All messages (Command + Event) go through `exchange.bind_subscriber_callbacks` -> `queue.put()` -> consumer `queue.take()` -> `create_task(_process_and_complete)`.
`execute(msg)` = `dispatch(msg)` + `await msg.state` (syntactic sugar).
Exchange subscriber callbacks bind only on Events (`isinstance(message, BaseEvent)`).

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

`registry` is a `Proxy` over `LocalStack` — pushed during `Bootstrap.__init__`, provides `commands`, `subscribers`, `resolve`, `resolve_app`, `get_app`.

## Destination & Topic

Format: `domain.ServiceAlias.CommandAlias` (3-part topic).

- Commands without explicit `destination` are bound via dynamic subclass at registration time: `type(Name, (OriginalCls,), {'destination': dest})`. Original class stays unchanged.
- `registry.resolve_app(msg)` reads `type(msg).destination` and takes first two segments to find the owning service from `services`.
- Exchange uses full destination as topic for pattern matching.

## Exchange (pub/sub)

Subscriber values are **method names** (str or list) pointing to methods on the AppService. RegistryService generates handler Commands at startup and maintains subscribers; Exchange is a stateless routing trigger.

```python
class DataEngine(AppService):
    subscribers = {
        'analytics.*.DataReady': 'on_data_ready',                   # single method
        'trading.DataEngine.BarsReady': ['on_bars', 'update_cache'], # fan-out: both run in parallel
    }

    async def on_data_ready(self, message):
        ...

    async def on_bars(self, message): ...
    async def update_cache(self, message): ...
```

TOML:

```toml
["trading.app.DataEngine".subscribers]
"analytics.*.DataReady" = "on_data_ready"
"trading.DataEngine.BarsReady" = ["on_bars", "update_cache"]
```

### Registration (RegistryService)

During `registry.register()`, subscriber configs are scanned. For each `(topic, method_name)`, a dynamic Command class wrapping the bound method is generated, stored in `registry.commands`, and the topic→destination mapping is stored in `registry.subscribers`.

### Routing (Exchange)

Exchange reads `registry.subscribers` at runtime — no local state. `bind_subscriber_callbacks(msg)` adds done-callbacks to Event's state Future. When Event completes, `_on_subscriber_done` resolves the handler via `registry.resolve(destination)`, instantiates it with `_source = original_msg`, and dispatches it through Hub.

- Callback signature: `async def method(self, message)` — self = AppService instance, message = the source Event instance.
- AMQP-style wildcards: `*` = one segment, `#` = zero or more.
- Multiple instances subscribing to the same topic → each instance's handlers dispatch independently in parallel.
- Runtime subscribe/unsubscribe via `registry.subscribe(topic, dest)` / `registry.unsubscribe(topic, dest)`.

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
    depends = ['infra.ConfigEngine']                            # resolved to instances at startup
    subscribers = {'trading.*.BarsReady': 'on_bars_ready'}      # method name, not Command class

    async def on_bars_ready(self, message):
        event = message.get_event()
        self.transform(event['data'])

    def transform(self, data):
        return processed_data  # business method called by Commands
```

Key rules:
- `protocol` is auto-assigned when `add_dependency` receives a `Protocol` instance.
- Service registry is the `services` MutableMappingProxy (`globals.services`), keyed by `{domain}.{alias}`. Populated by Bootstrap.
- `RegistryService` manages all command bindings (`commands`) and event subscriptions (`subscribers`). Accessible globally via `globals.registry`.
- `create_from(**conf)` merges TOML config (`commands`, `routers`, `subscribers`, `depends`) with class-level defaults.
- `registry.resolve_app(message)` reads `type(msg).destination` and uses first two segments to find the owning service from `services`.
- Commands access the owning service via `globals.app`; never reach into sub-services.

## Protocol System

### Base class

`Protocol(BaseService)` — lifecycle managed by `mode.Service`. Subclasses implement `on_start` (init adapter), `on_stop` (cleanup), `__aenter__`/`__aexit__` (connection scope).

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

### Structure

```toml
["myapp.app.MyService"]
commands = ["commands", "extra_commands"]

["myapp.app.MyService".routers]
Ping = ["GET",  "/api/ping"]
Echo = ["POST", "/api/echo"]
Stream = ["SSE", "/api/stream"]

["myapp.app.MyService".subscribers]
"analytics.*.DataReady" = "on_data_ready"
"trading.DataEngine.BarsReady" = ["on_bars", "update_cache"]

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
| `routers` | `dict` | `cls.routers` ClassVar |
| `subscribers` | `dict` | `{topic: method_name \| [method_names]}` merged into `cls.subscribers` |
| `depends` | `list[str]` | Resolved to `dict[str, AppService]` after all services created. Access via `self.get_dependency("domain.alias")` |
| `protocol` | `dict` | Instance `protocol` via `add_dependency` |
| other keys | any | Passed as `**kwargs` to `__init__` |

### Parameter Management

TOML keys are split into two categories:

1. **Framework-level keys** (`commands`, `routers`, `subscribers`, `depends`, `protocol`) — always defined in TOML when needed. These control framework wiring.
2. **Service-level custom parameters** — defined as `__init__` parameters with defaults in the service/protocol class itself. TOML only overrides values that differ from defaults.

**Principle**: TOML should be minimal. If a service parameter equals its class default, omit it from TOML. Custom parameters belong in each service's `__init__` signature with sensible defaults; TOML's role is override, not definition.

```toml
# Good: only override non-default values
["myapp.strategy.FibStrategy"]
subscriber = {"analysis.Engine.SignalEmitted" = "on_signal"}
# position_size and min_strength use class defaults, not listed

# Good: protocol parameters that differ from defaults
["myapp.app.MyService".protocol]
module = "bollydog.adapters.memory.SQLiteProtocol"
path = "data/custom.db"

# Bad: repeating default values
["myapp.strategy.FibStrategy"]
position_size = 0.1      # ← this is already the class default, remove it
min_strength = 0.6        # ← same, remove it
```

### Service lifecycle

Bootstrap handles config loading and service instantiation in a single `_build_services` method:

```
Bootstrap(mode.Worker)
  __init__(config=path)
    -> _build_services(): read TOML, merge SERVICE_CONFIG, iterate sections
       -> cls.create_from(**conf) per section
       -> resolve depends: string refs -> AppService instances, add_dependency
    -> returns BollydogServices(dict) with typed property accessors (.registry, .hub, .session, .executor)
    -> push all context stacks: services, registry, session, hub

  on_first_start
    -> install signals

  on_started
    -> if _message set (execute mode): services.executor.execute -> stop
    -> else: maybe_start all services, log commands + subscribers

  on_shutdown -> services.clear()

HubService(CommandRunnerMixin, AppService)
  on_first_start       -> push hub onto _hub_ctx_stack
  exchange/queue       -> lazy property, resolved from services dict
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

Each module owns its own config via `os.getenv`, prefixed by module name (no global `BOLLYDOG_` prefix).

### Command (models/base.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `COMMAND_EXPIRE_TIME` | `3600` | Command timeout (s) |
| `COMMAND_DEFAULT_SIGN` | `1` | Soft-delete marker (1=normal, -1=deleted) |
| `COMMAND_DELIVERY_COUNT` | `0` | Retry count on timeout |

### Service (service/config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `QUEUE_MAX_SIZE` | `1000` | Queue capacity |
| `QUEUE_HISTORY_MAX_SIZE` | `1000` | Queue history length |

### Entrypoint Toggle (each entrypoint's config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENTRYPOINT_HTTP_ENABLED` | `0` | Enable HTTP entrypoint |
| `ENTRYPOINT_WS_ENABLED` | `0` | Enable WebSocket entrypoint |
| `ENTRYPOINT_UDS_ENABLED` | `0` | Enable UDS entrypoint |

### Entrypoint HTTP (entrypoint/http/config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENTRYPOINT_HTTP_SERVICE_HOST` | `0.0.0.0` | Listen address |
| `ENTRYPOINT_HTTP_SERVICE_PORT` | `8000` | Listen port |
| `ENTRYPOINT_HTTP_SERVICE_DEBUG` | `False` | Debug mode |
| `ENTRYPOINT_HTTP_SERVICE_LOG_LEVEL` | `info` | Log level |

### Entrypoint WebSocket (entrypoint/websocket/config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENTRYPOINT_WS_SERVICE_HOST` | `0.0.0.0` | Listen address |
| `ENTRYPOINT_WS_SERVICE_PORT` | `8001` | Listen port |
| `ENTRYPOINT_WS_SERVICE_DEBUG` | `False` | Debug mode |
| `ENTRYPOINT_WS_SERVICE_LOG_LEVEL` | `info` | Log level |

### Entrypoint UDS (entrypoint/uds/config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENTRYPOINT_UDS_SOCK_PATH` | `/tmp/bollydog.sock` | Unix domain socket path |
| `ENTRYPOINT_UDS_SEND_DEFAULT_CONFIG` | - | Default send config |

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
| subscriber not triggered | Verify `subscribers` config in TOML; check `registry.subscribers` |
