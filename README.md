# TODO

- [ ] ftr:支持handlers的类
- [ ] ftr:bollydog service支持exclude
- [X] ftr:support Message AsyncIterator

# TODO 按需增加

- [ ] ftr:entrypoint增加一个开关，能够开启或者关闭接收特定消息
- [ ] ftr:rete，和开关特性是否一致？
- [ ] ftr:pydantic plugin 校验入参的预留关键词
- [ ] ftr:redis适配器，以支持发布订阅和事件提交
- [ ] ftr:router_mapping增加别名的路由地址
- [ ] ftr:orm适配器同时支持domain和原生model base
- [ ] ftr:热重载
- [ ] ftr:标签label
- [ ] ftr:otlp
- [ ] ftr:优先级

# 环境变量

全局
BOLLYDOG_MESSAGE_EXPIRE_TIME
BOLLYDOG_IS_DEBUG
BOLLYDOG_HANDLERS
BOLLYDOG_BUS_SERVICE_PROTOCOL
BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK
BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK_URL

loguru 日志配置
LOGURU_FORMAT

http api服务
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


# 工程结构

> 遵照python的DDD的范式实现
> 参考来自 [__Architecture Patterns with Python__](https://www.cosmicpython.com/book/preface.html)
> 参考来自 [__Faust__](https://github.com/robinhood/faust)
> 参考来自 [twisted](https://github.com/twisted/twisted)


# 使用说明

 `bollydog command` 实例化一条message并调用对应handler执行  
 `bollydog execute` 执行一条实例化好的message并调用对应的handler执行
 `bollydog service` 启动编排好的各项服务，只有通过服务处理的事件才会被发布，订阅者才能感知, 允许protocol为空  
 `python -m fire bollydog.entrypoint.cli CLI shell`  

# 交互式客户端

```shell
ptpython --asyncio
```