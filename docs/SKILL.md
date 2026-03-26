---
name: bollydog-framework
description: bollydog AI 速查：Command 两条加载路径、AppService.commands 显式绑定、globals 与 destination 上下文、Command/Service 边界。
---

# Bollydog — AI 速查

细节见 [README.md](../README.md)。

## 概念

`BaseCommand`（`__call__`）→ `Hub` 调度；`AppService`（`router_mapping`、可选 `protocol`）；`destination` = 目标 `domain.alias`。链：`入口 → Hub → Session → Command.__call__`。

## Command 加载：两条路径

- **自动发现**（无依赖 app）：项目根下的 `commands.py` 或 `commands/` 包，`get_apps` 启动时自动 `smart_import('commands')`。这些 Command 的 `destination = None`，不绑定任何 AppService。
- **显式绑定**（依赖 app）：通过 `AppService.commands` ClassVar 或 YAML `commands:` 字段声明模块列表。`create_from` 调用 `_load_commands` 加载模块，**自动**将新注册的 Command 的 `destination` 设为该 AppService 的 `domain.alias`。

不再需要手写 `destination`。显式写 `destination = None` 可强制不绑定；显式写 `destination = 'other.service'` 可跨域绑定。

## Command / AppService 边界

- **Command**：流程与编排（顺序、`yield` 子命令）；宜薄。
- **AppService**：绑定在本域的**实例方法**（资源、领域操作）；Command 通过 **`globals.app`** 调用。
- **数据**：Command ↔ Service 用**基础/可 JSON 类型**（`dict/list/str/...`），少传 ORM/大对象。

## globals（重要）

- **用 `hub`、`app`、`protocol`、`message`、`session`**，**不要** `import` Service **类**当单例或静态入口。
- **`app` 由 `destination` 解析到 `Hub.apps[domain.alias]`**，随命令而变；跨域用 `await hub.dispatch(cmd)` 或 `hub.apps['x.y']`。

## 布局与配置

- `AppService` 放 `myapp/app.py`，该服务的命令模块在 `commands` 字段中声明。YAML 顶层 **domain**，块内 `app: !module pkg.mod.Class`。
- **`commands`**（默认 `[]`）：`create_from` 里 `_load_commands` 加载模块并绑 destination；YAML 可覆盖。无 `.` 则拼 `{AppService 包名}.{名}`，有 `.` 为完整模块路径。
- 无依赖 Command 放项目根 `commands/` 即可，无需在任何 AppService 中声明。
- **`!module`** 类须存在；**`protocol.module`** 用真实 Adapter 类名；**`!env`** 替换 `${VAR}`。

## Command 示例

```python
# 有依赖（由 AppService.commands 加载，destination 自动绑定）
class Ping(BaseCommand):
    async def __call__(self, *args, **kwargs):
        return {"ok": True}

# 无依赖（放项目 commands/ 下，destination = None）
class Pipeline(BaseCommand):
    async def __call__(self, *args, **kwargs):
        result = yield Ping()
        yield {"final": result}
```

`router_mapping` 的 key = **类名**；子命令在 generator 里 `yield SubCommand()`。

## CLI

```bash
bollydog ls --config ./config.yaml
bollydog execute <alias|fqn> --config ./config.yaml
bollydog service --config ./config.yaml
bollydog shell --config ./config.yaml
```

HTTP/WS 开关见 README 环境变量。

## 排查

| 现象 | 处理 |
|------|------|
| `ls` 无业务命令 | `--config`；检查 `commands` 字段是否包含命令模块 |
| `resolve` 失败 | 模块是否已加载；冲突用 FQN |
| `destination` 无解 | `domain.alias` 与 YAML / `Hub.apps` 一致 |
| `!module` 报错 | 符号在模块内真实存在 |
| 职责混乱 / 错 `app` | 流程在 Command、能力在 Service；只用 `globals.app` |

与 README 冲突时以 **源码 + 业务 YAML** 为准。
