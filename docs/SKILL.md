---
name: bollydog-framework
description: bollydog AI 速查：Command 两条加载路径、destination 即 Exchange topic、Exchange/Queue、globals 与 Command/Service 边界。
---

# Bollydog — AI 速查

细节见 [README.md](../README.md)。

## 概念

`BaseCommand`（`__call__`）→ `Hub` 调度；`AppService`（`router_mapping` HTTP 路由、可选 `protocol`、`subscribe` 订阅模式）；**`destination`** = 三段式 **topic**（`domain.ServiceAlias.CommandAlias`），未绑定默认为 `_._.CommandAlias`。链：`入口 → Hub → Session → Command.__call__`。

## destination（topic）

- **路由**：`Hub._resolve_app` 取 `destination` 的前两段 `domain.ServiceAlias` 在 `Hub.apps` 中查找；`_._` 表示无绑定 app。
- **Exchange**：`hub.emit`、命令执行完成后的 `publish` 均使用同一 `destination` 字符串作为 topic（AMQP 风格 `*` / `#` 通配）。
- 显式声明：旧两段 `domain.Service` 会在类定义时自动补成三段 `domain.Service.CommandAlias`。

## Command 加载：两条路径

- **自动发现**（无依赖 app）：项目根 `commands.py` 或 `commands/` 包，`get_apps` 时 `smart_import('commands')`。默认 `destination = '_._.CommandAlias'`。
- **显式绑定**：`AppService.commands` 或 YAML `commands:`。`_load_commands` 若 `destination` 以 `_._` 开头，则设为 `{domain}.{alias}.{CommandAlias}`。

## 订阅

- `AppService.subscribe: ClassVar[dict]` — `topic_pattern: method_name`，与 `commands` / `router_mapping` 一样支持 YAML 覆盖。
- 启动时 `Hub.on_started` 对 `exchange.subscribe` 注册。

## Command / AppService 边界

- **Command**：流程与编排；宜薄。
- **AppService**：绑定在本域的实例方法；Command 通过 **`globals.app`** 调用。
- **数据**：基础/可 JSON 类型。

## globals（重要）

- `hub`、`app`、`protocol`、`message`、`session`；**不要**把 Service 类当单例。
- **`app`** 由 `destination` 前两段解析；跨域用 `await hub.dispatch(cmd)` 或 `hub.apps['domain.ServiceAlias']`。

## 布局与配置

- YAML 顶层 **domain**，块内 `app: !module ...`；`commands`、`router_mapping`、`subscribe` 均可写在 YAML。
- 无依赖 Command 放项目根 `commands/`。
- **`!module`**、`protocol.module`、`!env` 规则不变。

## CLI

`bollydog ls` 列出 `TOPIC`（即 `destination`）。`execute` / `service` / `shell` 同前。

## 排查

| 现象 | 处理 |
|------|------|
| `ls` 无业务命令 | `--config`；检查 `commands` |
| `resolve` 失败 | 别名区分大小写（与类名一致）；冲突用 FQN |
| `destination` / app 无解 | 前两段须与 `Hub.apps` 的 key 一致 |
| 错 `app` | 只用 `globals.app` |

与 README 冲突时以 **源码 + 业务 YAML** 为准。
