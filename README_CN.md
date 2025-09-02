# 特性

- 协程
- 事件驱动，事件规范通过 `models.base:BaseMessage`
- 以 DDD 与 TDD 为基础的设计范式
- 相同的业务流，支持多个入口（CLI/HTTP/WebSocket 等）
- 通过 `models.base:Session` 提供全局上下文会话
- 基于配置文件的微服务式编排，使大型单体更结构化；无需改动代码即可支持负载均衡与系统拆分
- 使用异步生成器组织更复杂的原子流程调用
- 遵循 OpenTelemetry 范式：日志、追踪、指标
- 支持 Shell 交互环境
- 快速适配存量系统，非侵入式迭代与开发

# 核心概念

`Command`、`Event`、`Handler`、`UnitOfWork`、`Service`、`Protocol`、`Session`

# 核心待办

- [ ] ftr：IOC agent 作为入口，可如 API 一样调用全部 handlers
- [ ] ftr：热更新
- [ ] ftr：状态服务
  - [ ] ftr：标签支持
  - [ ] ftr：rete
- [ ] ftr：分布式服务
  - [ ] ftr：优先级系统
  - [ ] ftr：在 `router_mapping` 中新增别名路由
- [ ] ftr：遥测服务
  - [ ] ftr：opentelemetry
- [ ] ftr：Pydantic 插件，用于校验输入参数中的保留关键字
- [ ] ftr：服务构建器，便捷创建 AppService
- [X] ftr：自 0.1.3 起，`command` 仅绑定一个 handler，`event` 支持多播或重写；优化自动发现
- [X] ftr：支持 `.wheel` 安装与 `uv` 安装
- [X] opt：将 `bus` 重命名为 `hub`
- [ ] ftr：支持在上下文中等待其他 handler 产生的消息集合
- [ ] fix：SqlAlchemyAsyncUnitOfWork 缺陷，pytest 未通过

# 模块待办

- [ ] opt：WebSocket 中间件
- [ ] ftr：在入口增加开关，用于启停接收特定消息（分布式服务）
- [ ] ftr：HTTP 消息防抖或 QoS

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

# 设计

> [__Architecture Patterns with Python__](https://www.cosmicpython.com/book/preface.html) 作为基础设计范式。

![Architecture Patterns with Python](https://www.cosmicpython.com/book/images/apwp_aa01.png)

> [__`mode` 模块__](https://github.com/faust-streaming/mode) 作为底层应用框架。

定义了核心执行逻辑。

![architecture](./docs/architecture.jpg)

# 使用方式（HOW）

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

## 构建

```shell
uv build --all
uv run uv pip install dist/bollydog-*.whl
bollydog --help

```

# CLI

```shell
# 执行单条消息
cd bollydog/example
bollydog execute --config='./config.yaml' --message=example.handler.TaskCount
```

```shell
# 按配置启动服务  
bollydog service --config "./config.yaml"
curl http://0.0.0.0:8000/example/exampleservice/taskcount
```

```shell
# 交互式 shell
bollydog shell --config "./config.yaml"
```

```python
locals()
from example.handler import TaskList,task_list
await task_list(TaskList())
```

# 使用案例（Using Case）

## 使用内置 SqlAlchemyProtocol 的 CRUD（无需自定义 Protocol 类）

```python
# 本示例展示如何直接依赖 SqlAlchemyProtocol 的内置 CRUD
# 从而省略自定义 ExampleProtocol。
# 内容包含：消息、模型、服务、处理器，以及示例配置。

# 1) 消息（Command/Event）
from bollydog.models.base import Command, Event

class CreateUser(Command):
    username: str
    email: str

class UserCreated(Event):
    user_id: int

# 2) SQLModel 领域实体与 metadata
from typing import Optional
from sqlmodel import SQLModel, Field
from bollydog.adapters.rdb import SQLModelDomain

class User(SQLModel, SQLModelDomain, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: str

# 在 UnitOfWork 配置中使用 SQLModel.metadata
metadata = SQLModel.metadata

# 3) 领域 AppService
from bollydog.models.service import AppService

class ExampleService(AppService):
    domain = "example"

# 4) 处理器直接使用注入的 `protocol`
#    SqlAlchemyProtocol 已内置：add/get/list/update/delete/search
from bollydog.globals import protocol, session

async def create_user(cmd: CreateUser) -> UserCreated:
    # 可选审计
    session.username = session.username or "system"

    # 使用内置 CRUD 创建用户
    created = await protocol.add(User(username=cmd.username, email=cmd.email))

    # 如需，演示 `get` 取回数据
    row = await protocol.get(User, id=created.id)

    return UserCreated(user_id=row["id"] if isinstance(row, dict) else row.id)
```

最小装配配置（YAML，示意）

```yaml
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

## 完整示例（覆盖 Command/Event/Handler/Protocol/AppService 与全局对象）

```python
# 该端到端示例包含：
# - Command / Event 定义
# - 自定义 Protocol（内部复用内置 SqlAlchemyProtocol 的能力）
# - 一个 AppService
# - 在处理器中使用所有全局对象：hub、message、protocol、session、app
# - 如何通过 hub.execute() 串联消息

# 1) 消息
from bollydog.models.base import Command, Event

class UpdateUserEmail(Command):
    user_id: int
    new_email: str

class UserEmailUpdated(Event):
    user_id: int
    new_email: str

# 2) 领域模型
from typing import Optional
from sqlmodel import SQLModel, Field
from bollydog.adapters.rdb import SQLModelDomain

class User(SQLModel, SQLModelDomain, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: str

# 3) 自定义 Protocol（包装内置 CRUD）
from bollydog.adapters.rdb import SqlAlchemyProtocol

class Example2Protocol(SqlAlchemyProtocol):
    async def update_user_email(self, user_id: int, new_email: str):
        # 使用内置 `update` 修改 email 字段
        await self.update(User, user_id, email=new_email)
        # 返回标准化结果
        row = await self.get(User, id=user_id)
        return row

# 4) AppService
from bollydog.models.service import AppService

class Example2Service(AppService):
    domain = "example2"

# 5) 在处理器中使用所有全局对象
from bollydog.globals import hub, message, protocol, session, app

async def update_user_email(cmd: UpdateUserEmail) -> UserEmailUpdated:
    # session：记录操作者
    session.username = session.username or "operator"

    # app：服务内日志
    app.logger.info(f"updating user={cmd.user_id} -> {cmd.new_email}")

    # protocol：调用领域端口
    row = await protocol.update_user_email(cmd.user_id, cmd.new_email)

    # message：追踪/关联调试
    app.logger.debug(f"trace={message.trace_id} span={message.span_id}")

    # 如需：同步串联消息
    # await hub.execute(SomeFollowUpCommand(...))

    return UserEmailUpdated(user_id=row["id"] if isinstance(row, dict) else row.id,
                            new_email=row["email"] if isinstance(row, dict) else row.email)

async def on_user_email_updated(evt: UserEmailUpdated):
    # 全局对象在此仍可使用
    app.logger.info(f"updated user={evt.user_id} to {evt.new_email} by {session.username}")
    app.logger.debug(f"handled event={message.name} iid={message.iid}")
```

### 最小装配配置（示意）

```yaml
example2:
  app: !module app.example2.service.Example2Service
  unit_of_work:
    module: !module bollydog.adapters.rdb.SqlAlchemyAsyncUnitOfWork
    url: postgresql+asyncpg://user:pass@localhost:5432/demo
    metadata: !module app.example.store.metadata  # 可复用或自定义
  protocol:
    module: !module app.example2.protocol.Example2Protocol
  handlers:
    - app.example2.handler
```
