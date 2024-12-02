# TODO

- [ ] ftr: support handler message be waited in collection from other handlers message by ctx
- [ ] ftr: files database on hard disk
- [X] ftr: global session on entrypoint
- [X] fix: adapters create logic
- [ ] fix: SqlAlchemyAsyncUnitOfWork bug, pytest not pass
- [ ] opt: websockets middleware
- [ ] ftr: on 0.1.3, `command` can decorate a function to be a command implicit

# TODO MAYBE

- [ ] ftr: anonymous message call handler or generator
- [ ] ftr:entrypoint增加一个开关，能够开启或者关闭接收特定消息
- [ ] ftr:rete，和开关特性是否一致？
- [ ] ftr:pydantic plugin 校验入参的预留关键词
- [ ] ftr:redis适配器，以支持发布订阅和事件提交
- [ ] ftr:router_mapping增加别名的路由地址
- [ ] ftr:orm适配器同时支持domain和原生model base
- [ ] ftr:热重载
- [ ] ftr:标签label
- [ ] ftr:otlp
- [ ] opt: structlog
- [ ] ftr:优先级

# .env

global  
BOLLYDOG_MESSAGE_EXPIRE_TIME
BOLLYDOG_IS_DEBUG
BOLLYDOG_HANDLERS
BOLLYDOG_BUS_SERVICE_PROTOCOL
BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK
BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK_URL

logger  
LOGURU_FORMAT

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


# design 

> [__Architecture Patterns with Python__](https://www.cosmicpython.com/book/preface.html)
> [mode](https://github.com/faust-streaming/mode)

# cli

 `bollydog execute --config='./config.yaml' --message=service.model.TaskCount` run a command
 `bollydog service --config "./config.yaml"` start up service as config.yml  
 `bollydog shell --config "./config.yaml" ` 

```shell
ptpython --asyncio
```