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
        subs = registry.subscribers
        if subs:
            lines = '\n  '.join(f'{t} -> [{", ".join(destinations)}]' for t, destinations in subs.items())
            self.logger.info(f'subscribers({sum(len(v) for v in subs.values())}):\n  {lines}')
        await super().on_started()

    def match(self, topic: str) -> set:
        """Match topic against registry.subscribers, return set of handler destinations."""
        matched = set()
        for pattern, destinations in registry.subscribers.items():
            if pattern == topic or match_topic(pattern, topic):
                matched.update(destinations)
        return matched

    def _on_subscriber_done(self, destination, source_message, state):
        try:
            if self.should_stop: return
            if state.cancelled() or state.exception(): return
            handler = registry.resolve(destination)
            command = handler()
            command._source = source_message
            self.add_future(hub.dispatch(command))
        except Exception as e:
            self.logger.exception(f'subscriber callback error: {e}')

    def bind_subscriber_callbacks(self, message):
        if not isinstance(message, BaseEvent): return
        topic = type(message).destination
        if not topic: return
        for destination in self.match(topic):
            message.state.add_done_callback(partial(self._on_subscriber_done, destination, message))
