# Bollydog

Async microservice framework built on [mode](https://github.com/faust-streaming/mode), with the Command Pattern at its core, unifying HTTP / WebSocket / CLI entrypoints.

> Design paradigm inspired by [Architecture Patterns with Python](https://www.cosmicpython.com/book/preface.html)

## Features

- Coroutine-driven, powered by `asyncio` + `mode.Service` lifecycle management
- **Command as executable** — `BaseCommand` carries business logic directly via `async def __call__`, no external Handler needed
- **Polymorphic State** — regular commands use `asyncio.Future`, async generator commands automatically switch to `StreamState` (compatible with both `await` and `async for`)
- **Unified entrypoints** — the same Command can be executed via HTTP, WebSocket, CLI, or Shell
- **Queue message lifecycle** — PENDING → IN_FLIGHT → DONE / FAILED, with fixed-length history queue
- **Session context isolation** — each Command gets independent context keyed by `trace_id`, with pluggable Memory / Redis backends
- **SSE streaming** — async generator commands natively support Server-Sent Events
- **Orchestration** — `yield` sub-commands inside an async generator; Hub automatically dispatches and `asend`s the result back
- **Zero-YAML startup** — core services (HTTP / WS) are toggled via environment variables, no config file required
- OpenTelemetry paradigm: trace_id / span_id / parent_span_id tracing
- Interactive Shell environment

## Core Concepts

| Concept | Module | Description |
|---|---|---|
| `BaseCommand` | `models.base` | Executable command base class, defines `__call__`, auto-registers into `_registry` |
| `BaseEvent` | `models.base` | Event base class, inherits `BaseCommand`, excluded from registry |
| `StreamState` | `models.base` | Streaming state object, inherits `asyncio.Queue` and implements the `Future` interface |
| `BaseService` | `models.service` | Service base class, inherits `mode.Service`, auto-derives `domain` and `alias` |
| `AppService` | `models.service` | Application service base class, supports `protocol` injection and `router_mapping` declaration |
| `Protocol` | `models.protocol` | Adapter abstract base class, subclasses implement `create()` to initialize underlying connections |
| `Hub` | `service.app` | Central dispatcher, manages Exchange / Session / Queue / AppService |
| `Queue` | `service.queue` | Message queue management, FIFO scheduling + state tracking + history archival |
| `Session` | `service.session` | Context management service, isolates `SessionContext` per `trace_id` |
| `Exchange` | `service.exchange` | Hub-internal pub/sub (AMQP-style topic `*` / `#`) |

## Architecture

```
CLI / HTTP / WebSocket
        │
        ▼
      Hub  ──── dispatch ──→  Queue.put (qos=0)
       │                         │
       │                         ▼
       │                      Queue.take → Hub._process_message
       │
       ├── execute ──→ Session.acquire → _execute → Session.release
       │                                    │
       │                          ┌─────────┴──────────┐
       │                     is_async_gen?          await coro
       │                          │
       │                    _iterate(gen)
       │                     ├── yield Command → dispatch (sub-command orchestration)
       │                     └── yield data    → state.put (streaming output)
       │
       ├── Exchange (internal pub/sub)
       ├── Session (context management)
       └── Queue (message lifecycle)
```

## Installation

```shell
git clone https://github.com/3sy11/bollydog.git
cd bollydog

# pip
pip install -e .

# uv
uv sync && uv sync --dev

# build & install
uv build --all
uv run uv pip install dist/bollydog-*.whl
bollydog --help
```

## Quick Start

### Define a Command

```python
# myapp/commands.py
from typing import Any
from bollydog.models.base import BaseCommand

class Ping(BaseCommand):
    # destination 默认为三段 topic；由 AppService.commands 加载时绑定为 myapp.MyService.Ping

    async def __call__(self, *args, **kwargs) -> Any:
        return {'pong': True}
```

### Define an AppService

```python
# myapp/service.py
from bollydog.models.service import AppService

class MyService(AppService):
    domain = 'myapp'
    router_mapping = {
        'Ping': ['GET', '/api/ping'],  # key is the Command class name
    }
```

### Streaming Command (async generator)

```python
class StreamDemo(BaseCommand):

    async def __call__(self, *args, **kwargs):
        for i in range(5):
            yield {'chunk': i}       # each yielded value is pushed via StreamState
```

`StreamState` is activated automatically: Hub `put`s each yielded value into `message.state`. Consumers can `async for value in message.state` to receive items incrementally, or `await message.state` to get all accumulated results at once.

### Sub-command Orchestration

```python
class Orchestrator(BaseCommand):

    async def __call__(self, *args, **kwargs):
        result = yield SubCommand(param='value')  # yield a sub-command; Hub dispatches and asends the result back
        yield {'final': result}
```

Hub's `_iterate` method intercepts yielded `BaseCommand` instances, automatically dispatches them, and passes the execution result back via `gen.asend(result)`. If a sub-command raises an exception, it is propagated via `gen.athrow(exc)`, allowing the generator to handle it with `try/except`.

## CLI

```shell
# list all registered commands
bollydog ls

# execute a command (full Hub lifecycle)
bollydog execute taskcount
bollydog execute myapp.commands.ping --param=value

# start services
bollydog service
bollydog service --config ./config.yaml
bollydog service --apps '["http","ws"]'

# interactive Shell
bollydog shell
bollydog shell --config ./config.yaml
```

### Command Resolution

`BaseCommand.resolve(name)` supports two lookup modes:
- **alias** — e.g. `taskcount`, matches directly when unambiguous
- **FQN** — e.g. `bollydog.service.commands.taskcount`, exact fully-qualified name match

## Route Mapping (router_mapping)

Declare `router_mapping` in `AppService` subclasses. `HttpService` aggregates all mappings from registered AppServices at startup and registers routes automatically.

```python
class MyService(AppService):
    router_mapping = {
        'Ping': ['GET', '/api/ping'],           # custom method and path
        'UserList': ['POST'],                    # method only, path auto-generated
        'StreamChat': ['SSE', '/api/chat'],      # SSE streaming endpoint
    }
```

**Value format** — `[methods, path]`, both optional:
- `methods`: string or list; `'SSE'` triggers `SseHandler`
- `path`: when `None`, auto-generates `/api/{domain}/{alias}` (if `destination` is set) or `/api/{alias}`

**YAML example**:

```yaml
myapp:
  app: !module myapp.service.MyService
  router_mapping:
    Ping: ['GET', '/api/ping']
    UserList: ['POST']
```

## Environment Variables

### Global (service/config.py)

| Variable | Default | Description |
|---|---|---|
| `BOLLYDOG_COMMAND_EXPIRE_TIME` | `3600` | Command timeout (seconds) |
| `BOLLYDOG_EVENT_EXPIRE_TIME` | `120` | Event timeout (seconds) |
| `BOLLYDOG_QUEUE_MAX_SIZE` | `1000` | Queue max capacity |
| `BOLLYDOG_HISTORY_MAX_SIZE` | `1000` | Queue history length |
| `BOLLYDOG_DEFAULT_SIGN` | `1` | Default sign flag |
| `BOLLYDOG_DELIVERY_COUNT` | `0` | Default retry count |
| `BOLLYDOG_DEFAULT_QOS` | `1` | Default QoS (0=async queue, 1=sync execute) |
| `BOLLYDOG_HTTP_ENABLED` | `0` | Enable HTTP service (0/1) |
| `BOLLYDOG_WS_ENABLED` | `0` | Enable WebSocket service (0/1) |

### HTTP (entrypoint/http/config.py)

| Variable | Default | Description |
|---|---|---|
| `BOLLYDOG_HTTP_SERVICE_HOST` | `0.0.0.0` | Listen address |
| `BOLLYDOG_HTTP_SERVICE_PORT` | `8000` | Listen port |
| `BOLLYDOG_HTTP_SERVICE_DEBUG` | `False` | Debug mode |
| `BOLLYDOG_HTTP_SERVICE_LOG_LEVEL` | `info` | Log level |
| `BOLLYDOG_HTTP_SERVICE_PRIVATE_KEY_PATH` | - | SSL private key path |
| `BOLLYDOG_HTTP_SERVICE_PUBLIC_KEY_PATH` | - | SSL certificate path |
| `BOLLYDOG_HTTP_SERVICE_LOOP` | `uvloop` | Event loop implementation |
| `BOLLYDOG_HTTP_SERVICE_HTTP` | `httptools` | HTTP parser |
| `BOLLYDOG_HTTP_SERVICE_LIMIT_CONCURRENCY` | `0` | Concurrency limit |
| `BOLLYDOG_HTTP_SERVICE_LIMIT_MAX_REQUESTS` | `2000` | Max requests |
| `BOLLYDOG_HTTP_SERVICE_TIMEOUT_KEEP_ALIVE` | `5` | Keep-Alive timeout |
| `BOLLYDOG_HTTP_SERVICE_BACKLOG` | `128` | TCP backlog |
| `BOLLYDOG_HTTP_MIDDLEWARE_SESSION` | `1` | Session middleware (0/1) |
| `BOLLYDOG_HTTP_MIDDLEWARE_AUTH` | `1` | Auth middleware (0/1) |
| `BOLLYDOG_HTTP_MIDDLEWARE_CORS` | `1` | CORS middleware (0/1) |
| `HTTP_MIDDLEWARE_SESSIONS_SECRET_KEY` | - | Session secret key |

### WebSocket (entrypoint/websocket/config.py)

| Variable | Default | Description |
|---|---|---|
| `BOLLYDOG_WS_SERVICE_HOST` | `0.0.0.0` | Listen address |
| `BOLLYDOG_WS_SERVICE_PORT` | `8001` | Listen port |
| `BOLLYDOG_WS_SERVICE_DEBUG` | `False` | Debug mode |
| `BOLLYDOG_WS_SERVICE_LOG_LEVEL` | `info` | Log level |

## Adapters

The framework uses the `Protocol` abstraction layer to interface with different storage backends:

| Adapter | Module | Purpose |
|---|---|---|
| `MemoryProtocol` | `adapters.local` | In-memory KV, default Session backend |
| `RedisProtocol` | `adapters.redis` | Redis KV, optional Session backend |
| `FileProtocol` | `adapters.local` | File read/write |
| `SqlAlchemyProtocol` | `adapters.rdb` | Relational database CRUD |
| `ElasticProtocol` | `adapters.elastic` | Elasticsearch |
| `Neo4jProtocol` | `adapters.neo4j` | Neo4j graph database |

## Global Context (globals)

Request-scoped context proxies via `LocalStack`, available directly inside `BaseCommand.__call__`:

```python
from bollydog.globals import hub, message, protocol, session, app

class MyCommand(BaseCommand):
    # destination 为 topic（如 myapp.MyService.MyCommand），前两段用于 Hub 解析 app

    async def __call__(self, *args, **kwargs):
        session.username        # current operator
        message.trace_id        # current trace ID
        app.logger.info(...)    # logger bound to the AppService
        await hub.dispatch(SubCommand())  # dispatch a sub-command
        await protocol.get(...)  # use the bound Protocol
```

| Proxy | Description |
|---|---|
| `hub` | Current Hub instance |
| `message` | Currently executing BaseCommand |
| `session` | Current SessionContext |
| `app` | AppService bound to the current Command |
| `protocol` | Protocol bound to the current AppService |

## Project Structure

```
bollydog/
├── models/
│   ├── base.py          # BaseCommand, BaseEvent, StreamState, _ModelMixin
│   ├── service.py       # BaseService, AppService
│   └── protocol.py      # Protocol abstract base class
├── service/
│   ├── app.py           # Hub (central dispatcher)
│   ├── queue.py         # Queue (message queue / lifecycle)
│   ├── session.py       # Session, SessionContext
│   ├── exchange.py      # Exchange (internal pub/sub)
│   ├── commands.py      # Built-in commands (TaskCount)
│   └── config.py        # Global environment variable config
├── entrypoint/
│   ├── cli/             # CLI entrypoint (fire)
│   ├── http/            # HTTP entrypoint (Starlette + uvicorn)
│   │   ├── app.py       # HttpHandler, SseHandler, HttpService
│   │   ├── config.py    # HTTP environment variables
│   │   └── middleware.py # Auth / Session / CORS middleware
│   └── websocket/       # WebSocket entrypoint (Starlette + uvicorn)
│       ├── app.py       # SocketService
│       └── config.py    # WS environment variables
├── adapters/            # Protocol implementations (local, redis, rdb, elastic, neo4j)
├── globals.py           # Global context proxies (hub, message, session, app, protocol)
├── bootstrap.py         # Worker bootstrap
├── exception.py         # Custom exceptions
└── utils/               # Utility functions
```

## TODO

- [ ] Telemetry service (OpenTelemetry integration)
- [ ] Priority queue
- [ ] WebSocket middleware
- [ ] User-defined middleware registration
- [ ] Production deployment guide (supervisord + nginx multi-process)
- [ ] if yaml has not router_mapping,disable HTTP service