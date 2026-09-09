"""Exchange: topic -> Event class index. Registration and instantiation only.

Dispatch is HubService.emit's job — Exchange holds no reference to hub or queue.
"""
from collections import defaultdict
from typing import Dict, List, Type

from bollydog.config import DOMAIN
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # topic (exact destination or wildcard pattern) -> Event classes
        self._events: Dict[str, List[Type[BaseEvent]]] = defaultdict(list)
        # destination -> Event class, for exact lookup by subscribe config
        self._classes: Dict[str, Type[BaseEvent]] = {}

    async def on_started(self) -> None:
        if self._events:
            lines = '\n  '.join(
                f'{topic:<40} -> [{", ".join(c.alias for c in classes)}]'
                for topic, classes in self._events.items()
            )
            self.logger.info(f'events({sum(len(v) for v in self._events.values())}):\n  {lines}')
        await super().on_started()

    def all_events(self) -> Dict[str, List[Type[BaseEvent]]]:
        """Return full topic -> Event classes index."""
        return self._events

    def add_event(self, topic: str, cls: Type[BaseEvent]):
        """Bind an Event class to a topic. Called once per class with its own
        destination at startup, then again per subscribe entry to alias it onto
        another topic."""
        if cls not in self._events[topic]:
            self._events[topic].append(cls)
        if cls.destination:
            self._classes[cls.destination] = cls

    def remove_event(self, topic: str, cls: Type[BaseEvent]):
        """Unbind an Event class from a topic."""
        if cls in self._events.get(topic, ()):
            self._events[topic].remove(cls)

    def resolve(self, destination: str) -> Type[BaseEvent]:
        """Exact destination lookup. Raises KeyError if not found."""
        if destination not in self._classes: raise KeyError(f"Event '{destination}' not found")
        return self._classes[destination]

    def match(self, topic: str) -> List[Type[BaseEvent]]:
        """Every Event class whose registered topic matches."""
        return [cls
                for pattern, classes in self._events.items()
                if pattern == topic or match_topic(pattern, topic)
                for cls in classes]

    def instantiate(self, topic: str) -> List[BaseEvent]:
        """Materialize every Event bound to topic. Dispatch is the caller's job."""
        return [cls() for cls in self.match(topic)]
