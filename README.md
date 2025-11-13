[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=for-the-badge&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/3sy11/bollydog)

# Features

- Coroutines
- Event-driven, event specification via `models.base:BaseMessage`
- DDD and TDD as fundamental design paradigms
- Same logical flow, multiple entrypoints
- Global context session via `models.base:Session`
- Microservice orchestration via configuration file, enabling a more structured large-scale monolith; supports load balancing and system decomposition without code changes
- Asynchronous generator mechanism for organizing more complex atomic process calls
- Opentelemetry paradigm: logging, tracing, metrics
- Shell environment support
- Fast adaptation to legacy projects, non-intrusive iteration and development

# Core Concepts

`Command`, `Event`, `Handler`, `UnitOfWork`, `Service`, `Protocol`, `Session`

# CORE TODO LIST

- [ ] ftr: IOC agent can be injected as an entrypoint, behaves like an API and can invoke all handlers
- [ ] ftr: hot reloading
- [ ] ftr: state service
  - [ ] ftr: label support
  - [ ] ftr: rete
- [ ] ftr: distribute service
  - [ ] ftr: priority system
  - [ ] ftr: add alias routing in `router_mapping`
- [ ] ftr: telemetry service
  - [ ] ftr: opentelemetry
- [ ] ftr: pydantic plugin to validate reserved keywords in input parameters
- [ ] ftr: service builder to create AppService
- [X] ftr: on 0.1.3, `command` combine to one handler, `event` combine to multi or rewrite, opt autodiscover
- [X] ftr: `.wheel` install support & `uv` install
- [X] opt: rename `bus` to `hub`
- [ ] ftr: support handler message be waited in collection from other handlers message by ctx
- [ ] fix: SqlAlchemyAsyncUnitOfWork bug, pytest not pass


# MODULE TODO LIST

- [ ] opt: WebSocket middleware
- [ ] ftr: add toggle in entrypoint to enable or disable receiving specific messages(distribute service)
- [ ] ftr: HTTP messages debounce or QoS

# .env

global  
BOLLYDOG_COMMAND_EXPIRE_TIME  
BOLLYDOG_EVENT_EXPIRE_TIME  
BOLLYDOG_LOG_LEVEL  
BOLLYDOG_HANDLERS   

http api  
BOLLYDOG_HTTP_SERVICE_HOST  
BOLLYDOG_HTTP_SERVICE_DEBUG  
BOLLYDOG_HTTP_SERVICE_PORT  
BOLLYDOG_HTTP_SERVICE_LOG_LEVEL  
BOLLYDOG_HTTP_SERVICE_PRIVATE_KEY  
BOLLYDOG_HTTP_SERVICE_PUBLIC_KEY  

websocket  
BOLLYDOG_WS_SERVICE_HOST  
BOLLYDOG_WS_SERVICE_DEBUG  
BOLLYDOG_WS_SERVICE_PORT  
BOLLYDOG_WS_SERVICE_LOG_LEVEL  


# DESIGN

> [__Architecture Patterns with Python__](https://www.cosmicpython.com/book/preface.html) Designed as a foundational design paradigm.

![Architecture Patterns with Python](https://www.cosmicpython.com/book/images/apwp_aa01.png)

> [__`mode` module__](https://github.com/faust-streaming/mode) Acts as a foundational application framework.

Defines the core execution logic.

![architecture](./docs/architecture.jpg)

# HOW

## pip

```shell
git clone https://github.com/3sy11/bollydog.git
pip install -e .
```

## uv 

```shell
git clone https://github.com/3sy11/bollydog.git
cd bollydog
uv sync
uv sync --dev
```

## build

```shell
uv build --all
uv run uv pip install dist/bollydog-*.whl
bollydog --help

```

# CLI

```shell
#execute a command  
cd bollydog/example
bollydog execute --config='./config.yaml' --message=example.handler.TaskCount
```

```shell
#start up service as config.yml  
bollydog service --config "./config.yaml"
curl http://0.0.0.0:8000/example/exampleservice/taskcount
```

```shell
# ptpython shell
bollydog shell --config "./config.yaml"
```

```python
locals()
from example.handler import TaskList,task_list
await task_list(TaskList())
```

# Using Case

## Using built-in SqlAlchemyProtocol CRUD (no custom Protocol class)

```python
# This example shows how to rely on SqlAlchemyProtocol's built-in CRUD
# so you can skip implementing a custom ExampleProtocol.
# It includes: messages, model, service, handler, and a sample config.

# 1) Messages (Command/Event)
from bollydog.models.base import Command, Event

class CreateUser(Command):
    username: str
    email: str

class UserCreated(Event):
    user_id: int

# 2) SQLModel domain entity and metadata
from typing import Optional
from sqlmodel import SQLModel, Field
from bollydog.adapters.rdb import SQLModelDomain

class User(SQLModel, SQLModelDomain, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: str

# We will use SQLModel.metadata in UnitOfWork config
metadata = SQLModel.metadata

# 3) AppService for domain
from bollydog.models.service import AppService

class ExampleService(AppService):
    domain = "example"

# 4) Handler uses the injected `protocol` directly
#    SqlAlchemyProtocol already provides: add/get/list/update/delete/search
from bollydog.globals import protocol, session

async def create_user(cmd: CreateUser) -> UserCreated:
    # optional auditing
    session.username = session.username or "system"

    # create a new User using built-in CRUD
    created = await protocol.add(User(username=cmd.username, email=cmd.email))

    # fetch it back if needed (demonstrates `get`)
    row = await protocol.get(User, id=created.id)

    return UserCreated(user_id=row["id"] if isinstance(row, dict) else row.id)
```

 Minimal config (YAML) to wire everything (illustrative)
``` yaml
example:
  app: !module app.example.service.ExampleService
  unit_of_work:
    module: !module bollydog.adapters.rdb.SqlAlchemyAsyncUnitOfWork
    url: postgresql+asyncpg://user:pass@localhost:5432/demo
    metadata: !module app.example.store.metadata
  protocol:
    module: !module bollydog.adapters.rdb.SqlAlchemyProtocol
  handlers:
    - app.example.handler
```

## Complete example covering Command/Event/Handler/Protocol/AppService and globals

```python
# This end-to-end example shows:
# - Command / Event definitions
# - A custom Protocol (wrapping built-in SqlAlchemyProtocol capabilities)
# - An AppService
# - Handlers using all globals: hub, message, protocol, session, app
# - How to chain messages via hub.execute()

# 1) Messages
from bollydog.models.base import Command, Event

class UpdateUserEmail(Command):
    user_id: int
    new_email: str

class UserEmailUpdated(Event):
    user_id: int
    new_email: str

# 2) Domain model
from typing import Optional
from sqlmodel import SQLModel, Field
from bollydog.adapters.rdb import SQLModelDomain

class User(SQLModel, SQLModelDomain, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: str

# 3) Custom Protocol (wrapping built-in CRUD)
from bollydog.adapters.rdb import SqlAlchemyProtocol

class Example2Protocol(SqlAlchemyProtocol):
    async def update_user_email(self, user_id: int, new_email: str):
        # Uses built-in `update` to modify the email field
        await self.update(User, user_id, email=new_email)
        # Return a normalized dict-like object to callers
        row = await self.get(User, id=user_id)
        return row

# 4) AppService
from bollydog.models.service import AppService

class Example2Service(AppService):
    domain = "example2"

# 5) Handlers using all globals
from bollydog.globals import hub, message, protocol, session, app

async def update_user_email(cmd: UpdateUserEmail) -> UserEmailUpdated:
    # session: carry operator information into auditing
    session.username = session.username or "operator"

    # app: log within current AppService
    app.logger.info(f"updating user={cmd.user_id} -> {cmd.new_email}")

    # protocol: call domain port
    row = await protocol.update_user_email(cmd.user_id, cmd.new_email)

    # message: inspect trace/span for debugging or correlation
    app.logger.debug(f"trace={message.trace_id} span={message.span_id}")

    # Chain another message synchronously if needed (example only)
    # await hub.execute(SomeFollowUpCommand(...))

    return UserEmailUpdated(user_id=row["id"] if isinstance(row, dict) else row.id,
                            new_email=row["email"] if isinstance(row, dict) else row.email)

async def on_user_email_updated(evt: UserEmailUpdated):
    # All globals still available in this handler
    app.logger.info(f"updated user={evt.user_id} to {evt.new_email} by {session.username}")
    # message: current envelope
    app.logger.debug(f"handled event={message.name} iid={message.iid}")
```

### Minimal config (illustrative)

```yaml
example2:
  app: !module app.example2.service.Example2Service
  unit_of_work:
    module: !module bollydog.adapters.rdb.SqlAlchemyAsyncUnitOfWork
    url: postgresql+asyncpg://user:pass@localhost:5432/demo
    metadata: !module app.example.store.metadata  # reuse or define your own
  protocol:
    module: !module app.example2.protocol.Example2Protocol
  handlers:
    - app.example2.handler
```
