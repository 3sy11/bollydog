from collections import defaultdict
from typing import ClassVar

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


class Exchange(AppService):
    domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._exact = defaultdict(set)
        self._patterns = defaultdict(set)
        self._hub = None

    async def on_started(self) -> None:
        for svc in self._hub.apps.values():
            for topic, handler in getattr(svc, 'subscriber', {}).items():
                self.subscribe(topic, handler)
        subs = {**self._exact, **self._patterns}
        if subs:
            lines = '\n  '.join(f'{t} -> [{", ".join(h.__name__ for h in hs)}]' for t, hs in subs.items())
            self.logger.info(f'subscriptions({sum(len(v) for v in subs.values())}):\n  {lines}')
        await super().on_started()

    def subscribe(self, topic: str, handler):
        if not (isinstance(handler, type) and issubclass(handler, BaseCommand)):
            raise TypeError(f'Exchange.subscribe only accepts Command classes, got {handler!r}')
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
