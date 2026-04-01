---
name: bollydog-framework
description: bollydog AI quick-ref — pipeline (_fire/_publish), Command loading, destination as Exchange topic, Exchange/Queue, data/events, globals, Command/Service boundary.
---

# Bollydog — AI Quick Reference

Details in [README.md](../README.md).

## Concepts

`BaseCommand`(`__call__`) → `Hub` dispatches; `AppService`(`router_mapping` HTTP routes, optional `protocol`, `subscribe` patterns); **`destination`** = 3-part **topic** (`domain.ServiceAlias.CommandAlias`), unbound defaults to `_._.CommandAlias`.

## Pipeline

`Hub.dispatch(message)` routes by type and qos:

| Path | Type | Routing | Queue | Publish |
|------|------|---------|-------|---------|
| Event | `BaseEvent` | `create_task(_fire)` | No | Yes |
| Command qos=0 | `BaseCommand` | `create_task(_fire)` | No | Yes |
| Command qos=1 | `BaseCommand` | `queue.put` → consumer | Yes | Yes |

### Execution methods

- `_fire(msg)`: `async with _with_context(msg)` → `_run` or `_run_gen` → `_publish(msg)`. Shared by Event and Command qos=0.
- `_run`: coroutine with retry loop. Pure execution, no context management.
- `_run_gen`: async generator, no retry. Handles `yield Command` (dispatch + send result back) and `yield value` (stream to state). Pure execution, no context management.
- `_process_queued(msg)`: `async with _with_context(msg)` → `_run`/`_run_gen` → `ack`/`nack` → `_publish(msg)`.
- `execute(msg)`: CLI direct mode. `async with _with_context(msg)` → `_run`/`_run_gen`. No elevate, no queue.
- `_with_context`: asynccontextmanager — session acquire/release + globals push/pop. Wraps execution at call sites, not inside `_run`/`_run_gen`.

### _publish

`Hub._publish(msg)` matches `type(msg).destination` via `exchange.match(topic)`:
- **Command class** handler → instantiate, `add_event(msg)`, dispatch

Runs **inside** `_with_context`, so handler Commands inherit trace correctly.

## Exchange (pub/sub, pure router)

- `exchange.subscribe(topic, handler)`: handler is **Command class** only.
- `exchange.match(topic) -> set`: returns matched handlers (exact + pattern).
- Exchange does **not** instantiate Commands or create tasks. Hub._publish handles that.
- AMQP-style wildcards: `*` = one segment, `#` = zero or more.

## data & events

`BaseCommand.data: dict`, general-purpose data field. `events` sub-key stores list of dict:

- `cmd.add_event(event)` → append `event.model_dump()`
- `cmd.get_event()` → latest `[-1]`; `get_event(0)` → earliest

Exchange handler Commands retrieve trigger event via `self.get_event()`.

## destination (topic)

- **Routing**: `Hub._resolve_app` takes first two segments `domain.ServiceAlias`; `_._` = unbound.
- **Fast-fail**: non-`_._` destination pointing to unregistered service raises `DestinationNotFoundError`.
- **Exchange**: `_publish` uses `destination` as topic for pattern matching.

## hub.get_service

`hub.get_service(cls_or_key, *, required=True)` — retrieve registered `AppService` by class, instance, or string key. Raises `ServiceNotFoundError` if `required=True` and not found.

## Command loading: two paths

- **Auto-discover**: project root `commands/`, `smart_import` during `get_apps`. Default `destination = '_._.CommandAlias'`.
- **Explicit binding**: `AppService.commands` or YAML. `_load_commands` rewrites `_._` prefix to `{domain}.{alias}.{CommandAlias}`.

## Subscriptions

- `AppService.subscribe: ClassVar[dict]` — `topic_pattern: CommandClass` only.
- YAML overridable. Registered in `Hub.on_started` to `exchange`.

## Command / AppService boundary

- **Command**: orchestration and flow; keep thin.
- **AppService**: domain-bound instance methods; Command calls via **`globals.app`**.
- **Data**: primitive / JSON-serializable types between them.

## globals (important)

- `hub`, `app`, `protocol`, `message`, `session`; **never** treat Service classes as singletons.
- **`app`** resolved from `destination` first two segments; cross-domain use `await hub.dispatch(cmd)`.

## Layout & Config

- YAML top-level **domain**, block `app: !module ...`; `commands`, `router_mapping`, `subscribe` all configurable in YAML.
- Unbound Commands go in project root `commands/`.
- `!module`, `protocol.module`, `!env` conventions unchanged.

## CLI

`bollydog ls` lists `TOPIC` (= `destination`). `execute` / `send` / `service` / `shell`.

## UDS entrypoint (optional)

- Env: `BOLLYDOG_UDS_ENABLED=1` registers `UdsService`. `BOLLYDOG_UDS_SOCK_PATH` (server bind). `BOLLYDOG_SEND_DEFAULT_CONFIG` optional default `--config` for `send`.
- Wire: length-prefixed JSON `{"command":"<alias>","kwargs":{}}` → server `resolve` → instance → `hub.dispatch` → `await msg.state`.
- `bollydog send <CommandAlias> <socket_path> ...` — **socket required**; `config` defaults from `BOLLYDOG_SEND_DEFAULT_CONFIG` or pass `--config`. Client: `UdsService(sock_path=socket).send(command, kwargs)`. In-process one-shot remains `execute`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ls` shows no commands | check `--config`; verify `commands` |
| `resolve` fails | alias is case-sensitive (matches class name); use FQN on conflict |
| destination / app unresolved | first two segments must match `Hub.apps` key |
| wrong `app` | always use `globals.app` |

When in doubt, source code + YAML config takes precedence.
