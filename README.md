# CORE

- [ ] ftr: support handler message be waited in collection from other handlers message by ctx
- [ ] fix: SqlAlchemyAsyncUnitOfWork bug, pytest not pass
- [ ] ftr: on 0.1.3, `command` can decorate a function to be a command implicit
- [ ] ftr: opentelemetry processer on strcutlog
- [X] opt: duckdb unit_of_work create_all ignore exist table
- [X] opt: redo `DOMAIN` argument
- [ ] ftr: rete?
- [ ] ftr: pydantic plugin 校验入参的预留关键词
- [ ] ftr: router_mapping增加别名的路由地址
- [ ] ftr: 热重载
- [ ] ftr: 标签label
- [ ] ftr: 优先级

# MODULE

- [ ] opt: websockets middleware
- [ ] ftr: entrypoint增加一个开关，能够开启或者关闭接收特定消息
- [ ] ftr: http messages debounce or qos

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

> [__Architecture Patterns with Python__](https://www.cosmicpython.com/book/preface.html)  
> [__`mode` module__](https://github.com/faust-streaming/mode)

# CLI

 `bollydog execute --config='./config.yaml' --message=service.model.TaskCount` execute a command  
 `bollydog service --config "./config.yaml"` start up service as config.yml  
 `bollydog shell --config "./config.yaml" `   

```shell
ptpython --asyncio
```