from collections import defaultdict
from typing import Any, Callable

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


class Exchange(AppService):
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._exact = defaultdict(set)
        self._patterns = defaultdict(set)

    def subscribe(self, topic: str, callback: Callable):
        store = self._patterns if ('#' in topic or '*' in topic) else self._exact
        store[topic].add(callback)

    def unsubscribe(self, topic: str, callback: Callable):
        store = self._patterns if ('#' in topic or '*' in topic) else self._exact
        store.get(topic, set()).discard(callback)

    async def publish(self, topic: str, message: Any):
        for cb in self._exact.get(topic, set()):
            await cb(message)
        for pattern, cbs in self._patterns.items():
            if match_topic(pattern, topic):
                for cb in cbs:
                    await cb(message)

    def list_topics(self):
        return {'exact': list(self._exact.keys()), 'patterns': list(self._patterns.keys())}
