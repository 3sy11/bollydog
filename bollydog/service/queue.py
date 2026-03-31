import asyncio
import logging
from collections import OrderedDict, deque
from typing import Optional, Tuple

from bollydog.models.base import BaseCommand as Message
from bollydog.models.service import AppService
from bollydog.service.config import QUEUE_MAX_SIZE, HISTORY_MAX_SIZE, DOMAIN
from bollydog.exception import ServiceMaxSizeOfQueueError

logger = logging.getLogger(__name__)

PENDING, IN_FLIGHT, DONE, FAILED = 1, 2, 0, 3


class Queue(AppService):
    domain = DOMAIN
    _store: OrderedDict[str, Tuple[Message, asyncio.Future, int]]
    _history: deque
    _notify: asyncio.Event

    def __init__(self, history_size=HISTORY_MAX_SIZE, **kwargs):
        super().__init__(**kwargs)
        self._store = OrderedDict()
        self._history = deque(maxlen=history_size)
        self._notify = asyncio.Event()

    async def put(self, message: Message) -> Message:
        if len(self._store) >= QUEUE_MAX_SIZE:
            raise ServiceMaxSizeOfQueueError(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} Queue is full')
        self._store[message.iid] = (message, message.state, PENDING)
        self._notify.set()
        return message

    async def take(self) -> Optional[Message]:
        while True:
            for iid, (msg, fut, status) in self._store.items():
                if status == PENDING:
                    self._store[iid] = (msg, fut, IN_FLIGHT)
                    return msg
            self._notify.clear()
            await self._notify.wait()

    def _archive(self, message_id: str, msg: Message, status: int):
        self._store.pop(message_id, None)
        self._history.append((message_id, msg, status))

    def ack(self, message_id: str, result=None):
        entry = self._store.get(message_id)
        if not entry:
            return
        msg, fut, _ = entry
        if not fut.done():
            fut.set_result(result)
        self._archive(message_id, msg, DONE)

    def nack(self, message_id: str, error: Exception):
        entry = self._store.get(message_id)
        if entry:
            msg, fut, _ = entry
            if not fut.done():
                fut.set_exception(error)
            self._archive(message_id, msg, FAILED)

    @property
    def has_pending(self) -> bool:
        return any(s == PENDING for _, _, s in self._store.values())

    @property
    def size(self) -> int:
        return len(self._store)
