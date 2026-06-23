# Exchange 轻量化 & Registry 统一管理 Event/Command

## 设计决策

- `_source` 机制保留（subscriber 方法需要拿到触发它的 Event 实例）
- Exchange 不维护自己的 `_exact/_patterns` 缓存，直接从 Registry 读取
- Command bindings 不持久化（来自代码扫描的静态结构）
- subscriptions 持久化关系字符串（topic→dest），不持久化闭包对象

## 变更文件清单

1. `bollydog/service/registry.py` — 新增 subscriptions + _register_subscribers
2. `bollydog/service/exchange.py` — 重写为轻量执行组件
3. `bollydog/bootstrap.py` — `_log_bindings` 增加 subscriptions 日志

---

## bollydog/service/registry.py

```python
"""RegistryService: centralized command/event binding and subscription index."""
from collections import defaultdict
from typing import Dict, Optional, Set, Type

from bollydog.config import DOMAIN
from bollydog.globals import services
from bollydog.models.base import BaseCommand, BaseEvent
from bollydog.models.service import AppService
from mode.utils.imports import smart_import


class RegistryService(AppService):
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bindings: Dict[str, Type[BaseCommand]] = {}
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)

    def register(self):
        """Scan all services, populate bindings and subscriptions."""
        for service_key, service in services.items():
            if service.commands_modules:
                self._register_commands(service_key, service)
            if service.subscriber:
                self._register_subscribers(service_key, service)
        self.logger.info(f'bindings({len(self.bindings)}) subscriptions({sum(len(v) for v in self.subscriptions.values())})')

    def _register_commands(self, service_key: str, service: AppService):
        """Scan service command modules, bind each Command/Event via dynamic subclass."""
        _pkg = type(service).__module__.rsplit('.', 1)[0]
        for module_name in service.commands_modules:
            _fqn = f'{_pkg}.{module_name}' if '.' not in module_name else module_name
            try: _mod = smart_import(_fqn)
            except (ImportError, ModuleNotFoundError, AttributeError): continue
            for _obj in vars(_mod).values():
                if not (isinstance(_obj, type) and issubclass(_obj, BaseCommand) and _obj not in (BaseCommand, BaseEvent)): continue
                if issubclass(_obj, BaseEvent) and 'destination' in _obj.__dict__: continue
                if not issubclass(_obj, BaseEvent) and '__call__' not in _obj.__dict__: continue
                dest = f'{service_key}.{_obj.alias}'
                bound = _obj if _obj.destination else type(_obj.__name__, (_obj,), {'destination': dest})
                self.bindings[dest] = bound

    def _register_subscribers(self, service_key: str, service: AppService):
        """Scan service subscriber config, generate handler Commands, populate subscriptions."""
        for topic, methods in service.subscriber.items():
            methods = [methods] if isinstance(methods, str) else methods
            for method_name in methods:
                bound_method = getattr(service, method_name, None)
                if bound_method is None:
                    raise AttributeError(f"{type(service).__name__} has no method '{method_name}'")
                dest = f'{service_key}.{method_name}'
                async def _call(self, _bm=bound_method): return await _bm(self._source)
                handler_cls = type(method_name, (BaseCommand,), {
                    'destination': dest, 'alias': method_name,
                    'module': type(service).__module__, '_source': None, '__call__': _call,
                })
                self.bindings[dest] = handler_cls
                self.subscriptions[topic].add(dest)

    def subscribe(self, topic: str, dest: str):
        """Runtime subscribe: add topic→dest mapping."""
        self.subscriptions[topic].add(dest)

    def unsubscribe(self, topic: str, dest: str):
        """Runtime unsubscribe: remove topic→dest mapping."""
        self.subscriptions.get(topic, set()).discard(dest)

    def resolve(self, destination: str) -> Type[BaseCommand]:
        """Exact destination lookup. Raises KeyError if not found."""
        if destination not in self.bindings: raise KeyError(f"Command '{destination}' not found")
        return self.bindings[destination]

    def resolve_app(self, msg: BaseCommand) -> Optional[AppService]:
        """Resolve owning AppService from message's class-level destination."""
        dest = type(msg).destination
        if not dest: return None
        return services.get('.'.join(dest.split('.')[:2]))

    def get_app(self, service_key: str) -> Optional[AppService]:
        """Lookup AppService by service_key (domain.alias)."""
        return services.get(service_key)
```

---

## bollydog/service/exchange.py

```python
"""Exchange: lightweight event routing and subscriber trigger."""
from functools import partial

from bollydog.config import DOMAIN
from bollydog.globals import hub, registry
from bollydog.models.base import BaseEvent
from bollydog.models.service import AppService


def _match(pp, tp, pi, ti):
    while pi < len(pp):
        if pp[pi] == '#':
            if pi == len(pp) - 1: return True
            for skip in range(ti, len(tp) + 1):
                if _match(pp, tp, pi + 1, skip): return True
            return False
        if ti >= len(tp): return False
        if pp[pi] != '*' and pp[pi] != tp[ti]: return False
        pi += 1; ti += 1
    return ti == len(tp)


def match_topic(pattern: str, topic: str) -> bool:
    """AMQP-style: * = one segment, # = zero or more segments."""
    return _match(pattern.split('.'), topic.split('.'), 0, 0)


class Exchange(AppService):
    domain = DOMAIN

    async def on_started(self) -> None:
        subs = registry.subscriptions
        if subs:
            lines = '\n  '.join(f'{t} -> [{", ".join(dests)}]' for t, dests in subs.items())
            self.logger.info(f'subscriptions({sum(len(v) for v in subs.values())}):\n  {lines}')
        await super().on_started()

    def match(self, topic: str) -> set:
        """Match topic against registry.subscriptions, return set of handler destinations."""
        matched = set()
        for pattern, dests in registry.subscriptions.items():
            if pattern == topic or match_topic(pattern, topic):
                matched.update(dests)
        return matched

    def _on_subscriber_done(self, dest, source_message, state):
        try:
            if self.should_stop: return
            if state.cancelled() or state.exception(): return
            handler_cls = registry.resolve(dest)
            command = handler_cls()
            command._source = source_message
            self.add_future(hub.dispatch(command))
        except Exception as e:
            self.logger.exception(f'subscriber callback error: {e}')

    def bind_subscriber_callbacks(self, message):
        if not isinstance(message, BaseEvent): return
        topic = type(message).destination
        if not topic: return
        for dest in self.match(topic):
            message.state.add_done_callback(partial(self._on_subscriber_done, dest, message))
```

---

## bollydog/bootstrap.py 变更（仅 `_log_bindings` 方法）

```python
    def _log_bindings(self):
        if not self.registry_service: return
        bindings = self.registry_service.bindings
        if bindings:
            _lines = '\n  '.join(f'{cmd_cls.alias:<20} -> {destination}' for destination, cmd_cls in bindings.items())
            self.logger.info(f'bindings({len(bindings)}):\n  {_lines}')
        subs = self.registry_service.subscriptions
        if subs:
            _lines = '\n  '.join(f'{t} -> [{", ".join(dests)}]' for t, dests in subs.items())
            self.logger.info(f'subscriptions({sum(len(v) for v in subs.values())}):\n  {_lines}')
```

---

## 变更总结

| 文件 | 变化 |
|------|------|
| `registry.py` | `_register` 拆为 `_register_commands` + `_register_subscribers`；新增 `subscriptions` 字典；新增 `subscribe`/`unsubscribe` 方法 |
| `exchange.py` | 删除 `__init__`/`_exact`/`_patterns`/`subscribe`/`unsubscribe`/`_make_callback`/`list_topics`；`match` 直接读 `registry.subscriptions`；`_on_subscriber_done` 通过 `registry.resolve(dest)` 获取 handler 类 |
| `bootstrap.py` | `_log_bindings` 新增 subscriptions 日志输出 |

## 不变的部分

- `HubService.dispatch` → `exchange.bind_subscriber_callbacks` 调用链不变
- `_source` 机制不变
- AMQP 通配匹配算法不变（`match_topic` 保留在 exchange.py）
- BaseCommand/BaseEvent 类结构不变
