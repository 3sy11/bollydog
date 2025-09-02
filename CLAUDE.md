## CLAUDE.md

This guide helps LLMs and Agents quickly understand the overall architecture of bollydog and explains how to use the framework to build new projects, refactor existing ones, and integrate into legacy systems with minimal intrusion. The framework design follows Architecture Patterns with Python (APP).

### Overview

- Goal: Compose core concepts via configuration—Service, Adapter, UnitOfWork, Protocol, Handler, Command, Event—to implement business functionality.
- Design mapping (APP → bollydog):
  - Command/Event → domain message model
  - Handler → application use cases / message handlers
  - UnitOfWork → transactional boundary / resource session
  - Protocol → ports exposing resource operations
  - Adapter → infrastructure adapters
  - Service/HubService/Router → in-process service orchestration and message bus
- Further reading: `docs/cosmic-python/Architecture Patterns with Python.md` and `docs/llms/mode.txt`.

### Quick Start

- Install & test:
```shell
uv sync
pytest
```
- Build & install:
```shell
uv build --all
uv run uv pip install dist/bollydog-*.whl
```
- Run example (load `example/config.yaml`):
```shell
uv run python -m bollydog.example.app
```

## Core Concepts and Code Mapping

### BaseMessage / Command / Event (message model)
- Location: `bollydog/models/base.py`
- Notes:
  - `BaseMessage`: unified envelope with tracing (`trace_id/span_id`) and `state: asyncio.Future` for results
  - `Command`: write intent with default `COMMAND_EXPIRE_TIME`
  - `Event`: change notification with default `qos=0` and event expiry
- Tip: message `name` defaults to class name in lower-case; read results via `message.state`.
- APP mapping: Commands drive writes; Events propagate domain changes (Ch. 10/12).

### Handler (use cases / message handlers)
- Location: `bollydog/service/handler.py`
- Notes:
  - `AppHandler.walk_module(module, app)`: scans module, auto-registers handlers based on parameter annotations
  - Command has at most one handler; Event supports multiple handlers
  - Forms:
    - async function: return next `Command/Event` or final result
    - async generator: yield multiple `Command/Event`, framework executes sequentially and backfills results
- Practice: keep orchestration in handlers; IO via Protocol/UoW only.
- APP mapping: Service layer + message bus dispatch (Ch. 8/9/10).

### UnitOfWork / Protocol (transaction boundary and ports)
- Location: `bollydog/models/protocol.py`
- Notes:
  - `UnitOfWork`: unified resource lifecycle with `connect()` context
  - `Protocol`: UoW-based ports exposing minimal operations
- Built-in RDB adapters: `bollydog/adapters/rdb.py`
  - `SqlAlchemyAsyncUnitOfWork`: SQLAlchemy Async UoW
  - `SqlAlchemyProtocol`: generic CRUD/query port
  - `DuckDBUnitOfWork`: embedded DuckDB for offline/transition scenarios
- APP mapping: Ports & Adapters + Unit of Work (Ch. 2/3/6).

### AppService / HubService / Router (services and bus)
- Location: `bollydog/models/service.py`, `bollydog/service/app.py`, `bollydog/service/router.py`
- Notes:
  - `AppService.create_from(domain, unit_of_work, protocol, handlers)`: construct services by config and register handlers
  - `HubService`: in-process message bus/scheduler; maintains queue and apps; publishes processed messages to `Router`
  - `Router`: pub/sub of message name to callbacks for cross-domain listeners or auditing
- Execution:
  - `hub.put_message()` enqueues async execution; `hub.execute()` executes immediately
  - Path (bus vs direct) chosen by current QoS/context
- APP mapping: message bus + service layer composition (Ch. 8/9/10/4).

## Configuration Orchestration (Entrypoints/Example)

- Example `example/config.yaml`:
```yaml
example:
  app: !module example.app.ExampleService
  handlers:
    - example.handler
http:
  app: !module bollydog.entrypoint.http.app.HttpService
  middlewares:
    -   middleware: !module starlette.middleware.sessions.SessionMiddleware
        secret_key: ${HTTP_MIDDLEWARE_SESSIONS_SECRET_KEY}
    -   middleware: !module starlette.middleware.authentication.AuthenticationMiddleware
        backend: !module bollydog.entrypoint.http.middleware.base_auth_backend
    -   middleware: !module starlette.middleware.cors.CORSMiddleware
        allow_origins: ["*"]
        allow_methods: ["*"]
        allow_headers: ["*"]
        max_age: 1728000
  router_mapping:
    answers.api.{item}.{command}: [POST, GET]
ws:
  app: !module bollydog.entrypoint.websocket.app.SocketService
```
- Tip: Use `!module` to declare services/handlers/middlewares by module path; HTTP/WS map routes to messages.

## Recipes

### Define a business use case (Command → Event)
1. Define `Command`/`Event` in a domain module
2. Implement handler (async function/generator) with parameter annotation of the message type
3. Assemble via `handlers=["your.module"]`
4. Send: `await hub.put_message(YourCommand(...))` or `await hub.execute(YourCommand(...))`

### Persistence access (Protocol/UoW)
1. Choose UoW (`SqlAlchemyAsyncUnitOfWork`/`DuckDBUnitOfWork`)
2. Call Protocol methods for CRUD/query from handlers; avoid coupling to ORM/SQL inside handlers

### Gradual legacy integration
- Wrap external API/DB in Adapters (create connection/client in `UnitOfWork.create()`)
- Expose minimal stable operations via Protocol; keep handlers orchestration-only

## APP quick cross-reference
- Message (Command/Event) → Ch. 10/12
- Message Bus/Handlers → Ch. 8/9/10
- Unit of Work → Ch. 6
- Repository/Adapter → Ch. 2/3/5 (expressed as Protocol/Adapter in this framework)
- Service Layer → Ch. 4

## Directory quick tour
- `bollydog/models/base.py`: message/service base classes
- `bollydog/models/protocol.py`: UoW and Protocol abstractions
- `bollydog/models/service.py`: app service base and factory
- `bollydog/service/handler.py`: handler discovery and dispatch
- `bollydog/service/app.py`: HubService (bus) and run loop
- `bollydog/service/router.py`: pub/sub for messages
- `bollydog/adapters/*.py`: infra adapters
- `bollydog/entrypoint/http|websocket`: external endpoints
- `example/config.yaml`: orchestration example

## Best Practices
- Cohesion by domain: co-locate messages/handlers/ports per domain
- Pure use cases: handlers call Protocol only, not infra directly
- Events first: prefer event-driven collaboration; use commands for explicit actions
- Config first: assemble by config for environment/parity switching and gradual upgrades
- Testability: handlers are pure async functions; Protocol/UoW can be replaced with in-memory versions for unit tests

