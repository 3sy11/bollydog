from collections import defaultdict

from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService
from bollydog.service.config import DOMAIN


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


def _make_callback(svc, method_name, bound_method):
    """Generate a Command class wrapping a bound service method."""
    dest = f'{svc.domain}.{svc.alias}.{method_name}'
    async def _call(self): return await bound_method(self)
    return type(method_name, (BaseCommand,), {'destination': dest, 'alias': method_name, 'module': type(svc).__module__, 'qos': 0, '__call__': _call})


class Exchange(AppService):
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._exact = defaultdict(set)
        self._patterns = defaultdict(set)

    async def on_started(self) -> None:
        for svc in AppService._apps.values():
            for topic, methods in svc.subscriber.items():
                methods = [methods] if isinstance(methods, str) else methods
                for method_name in methods:
                    bound = getattr(svc, method_name, None)
                    if bound is None:
                        raise AttributeError(f"{type(svc).__name__} has no method '{method_name}'")
                    cmd_cls = _make_callback(svc, method_name, bound)
                    self.subscribe(topic, cmd_cls)
                    self.logger.debug(f'subscribe {topic} -> {svc.domain}.{svc.alias}.{method_name}')
        subs = {**self._exact, **self._patterns}
        if subs:
            lines = '\n  '.join(f'{t} -> [{", ".join(h.destination or h.__name__ for h in hs)}]' for t, hs in subs.items())
            self.logger.info(f'subscriptions({sum(len(v) for v in subs.values())}):\n  {lines}')
        await super().on_started()

    def subscribe(self, topic: str, handler):
        store = self._patterns if ('#' in topic or '*' in topic) else self._exact
        store[topic].add(handler)

    def unsubscribe(self, topic: str, handler):
        store = self._patterns if ('#' in topic or '*' in topic) else self._exact
        store.get(topic, set()).discard(handler)

    def match(self, topic: str) -> set:
        matched = set()
        for h in self._exact.get(topic, set()):
            matched.add(h)
        for pattern, handlers in self._patterns.items():
            if match_topic(pattern, topic):
                matched.update(handlers)
        return matched

    def list_topics(self):
        return {'exact': list(self._exact.keys()), 'patterns': list(self._patterns.keys())}
