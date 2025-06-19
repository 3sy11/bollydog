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

- [ ] ftr: support handler message be waited in collection from other handlers message by ctx
- [ ] fix: SqlAlchemyAsyncUnitOfWork bug, pytest not pass
- [ ] ftr: on 0.1.3, `command` combine to one handler, `event` combine to multi or rewrite, opt autodiscover
- [ ] ftr: opentelemetry processor on structlog
- [ ] ftr: rete?
- [ ] ftr: pydantic plugin to validate reserved keywords in input parameters
- [ ] ftr: add alias routing in `router_mapping`
- [ ] ftr: hot reloading
- [ ] ftr: label support
- [ ] ftr: priority system
- [ ] ftr: IOC agent can be injected as an entrypoint, behaves like an API and can invoke all handlers
- [ ] ftr: `.wheel` install support
- [ ] opt: rename `bus` to `hub`

# MODULE TODO LIST

- [ ] opt: WebSocket middleware
- [ ] ftr: add toggle in entrypoint to enable or disable receiving specific messages
- [ ] ftr: HTTP messages debounce or QoS

# .env

global  
BOLLYDOG_MESSAGE_EXPIRE_TIME  
BOLLYDOG_LOG_LEVEL  
BOLLYDOG_HANDLERS  
BOLLYDOG_BUS_SERVICE_PROTOCOL  
BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK  
BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK_URL  

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

```shell
git clone https://github.com/3sy11/bollydog.git
pip install -e .

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
