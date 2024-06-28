# TODO

- [X] 重构用mode做服务编排
- [X] sqlalchemy adapter
- [X] starlette web 驱动
  - [X] 独立启动web 服务，uvicorn
- [X] message的command的返回值获取
- [X] 由bus加载app,重新编排
- [X] web服务handler功能
- [X] handler绑定在modules的app上，增加查找handler的机制
- ~~[ ] 修改iid为别名类型注释~~
- ~~[ ] 修改state为别名类型注释Literal~~
- ~~[ ] 多仓库机制~~
- [X] base protocol 先构造item 再交由adapters处理事务
- [X] webservice测试用例
- [X] 重构adapter，Adapter类里封装repository为unit_of_work，不再暴露
- [X] BootStrategy设计
- [X] protocol事件在关闭仓库时提交
- [X] app service create_from
- [X] 多action机制
- [X] entrypoint功能
- [X] 日志模块BUG，depth值不对
- [X] bootstrap用yaml进行微服务编排来启动, 用docker-compose兼容
- [X] 重写cli command方法逻辑
- [X] 增加event和command类
- ~~[ ] 使用router替换queue~~
- [ ] 支持handlers的类

# TODO 按需增加

- [X] logger缺少对exception的适配
- [X] 配置文件加载顺序，json->boot_strategy
- ~~[ ] 调整日志格式~~
- ~~[ ] 心跳~~
- [X] ftr:跟踪由messagehandler中生成的message，parent_message
- [X] opt:由domain生成orm
- [X] opt:对message的action做二次封装以适配各类消息协议
- [X] ftr:幂等
- [X] ftr:重试
- [X] opt:supervisor
- [X] ftr:valid功能
- [X] opt:分离服务配置和模块配置
- [ ] ftr:pydantic plugin 校验入参的预留关键词
- [ ] ftr:redis适配器，以支持发布订阅和事件提交
- [ ] ftr:router_mapping增加别名的路由地址
- [ ] ftr:orm适配器同时支持domain和原生model base
- [X] opt:重新组织测试用例
- [ ] ci:配置中心
- [X] ci:网关
- [ ] ftr:热重载
- [ ] ftr:标签label
- [ ] ftr:rete
- [ ] ftr:otlp
- ~~[ ] ftr:graphql~~
- [ ] ftr:优先级
- [ ] opt:git action
- [ ] opt:网关证书
- [X] opt:pydantic

# BUG

- crontab的定时任务会执行两次
- sqlalchemy代理session再register中执行del不会被删除

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

# ALL IN ONE

![architecture](./documents/architecture.png)
