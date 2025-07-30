# 特性

- 协程
- 事件驱动，事件规范`models.base:BaseMessage`
- DDD,TDD为基础设计范式
- same logical, multiple entrypoint
- 全局上下文会话`models.base:Session`
- 通过配置文件进行微服务编排，更规范的超大单体应用，在不修改代码实现负载均衡和拆分系统功能
- 异步生成器机制，可以组织更复杂的原子化的过程调用
- opentelemetry范式，日志、追踪、metric
- 支持shell环境运行
- 快速适配旧项目，非侵入式迭代和开发


# 核心概念

`Command`,`Event`,`Handler`,`UnitOfWork`,`Service`,`Protocol`,`Session`

# CORE TODO LIST

- [ ] ftr: support handler message be waited in collection from other handlers message by ctx
- [ ] fix: SqlAlchemyAsyncUnitOfWork bug, pytest not pass
- [X] ftr: on 0.1.3, `command` combine to one handler, `event` combine to multi or rewrite, opt autodiscover
- [ ] ftr: opentelemetry processer on strcutlog
- [ ] ftr: rete?
- [ ] ftr: pydantic plugin 校验入参的预留关键词
- [ ] ftr: router_mapping增加别名的路由地址
- [ ] ftr: 热重载
- [ ] ftr: 标签label
- [ ] ftr: 优先级
- [ ] ftr: IOC agent can be injected as a entrypoint, react like api and can call all handlers
- [X] ftr: .wheel install
- [X] opt: rename `bus` to `hub`

# MODULE TODO LIST

- [ ] opt: websockets middleware
- [ ] ftr: entrypoint增加一个开关，能够开启或者关闭接收特定消息
- [ ] ftr: http messages debounce or qos

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

> [__Architecture Patterns with Python__](https://www.cosmicpython.com/book/preface.html) 为基础设计范式

![Architecture Patterns with Python](https://www.cosmicpython.com/book/images/apwp_aa01.png)

> [__`mode` module__](https://github.com/faust-streaming/mode) 为基础应用框架

执行逻辑

![architecture](./docs/architecture.jpg)

# HOW

```shell
git clone https://github.com/3sy11/bollydog.git
pip install -e .
cd bollydog/example
```

# CLI

```shell
#execute a command  
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
