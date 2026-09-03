import asyncio
import logging
from collections import OrderedDict, deque
from typing import Optional, Tuple

from bollydog.config import DOMAIN, QUEUE_MAX_SIZE, QUEUE_HISTORY_MAX_SIZE
from bollydog.exception import ServiceMaxSizeOfQueueError
from bollydog.models.base import BaseCommand as Message
from bollydog.models.service import AppService

logger = logging.getLogger(__name__)

PENDING, IN_FLIGHT, DONE, FAILED, CANCELLED = 1, 2, 0, 3, 4


class Queue(AppService):
    domain = DOMAIN
    _store: OrderedDict[str, Tuple[Message, int, Optional[asyncio.Future]]]
    _history: deque
    _notify: asyncio.Event

    def __init__(self, history_size=QUEUE_HISTORY_MAX_SIZE, **kwargs):
        super().__init__(**kwargs)
        self._store = OrderedDict()
        self._history = deque(maxlen=history_size)
        self._notify = asyncio.Event()

    async def put(self, message: Message) -> Message:
        if len(self._store) >= QUEUE_MAX_SIZE:
            raise ServiceMaxSizeOfQueueError(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} Queue is full')
        self._store[message.iid] = (message, PENDING, None)
        self._notify.set()
        return message

    async def on_stop(self) -> None:
        self._notify.set()

    async def take(self) -> Optional[Message]:
        while True:
            for iid, (msg, status, _) in self._store.items():
                if status == PENDING:
                    return msg
            if self.should_stop: return None
            self._notify.clear()
            coro = await self.wait(self._notify.wait())
            if coro.stopped: return None

    def activate(self, iid: str, fut: asyncio.Future):
        """Mark message as IN_FLIGHT and bind its execution future. Called by Hub after add_future."""
        entry = self._store.get(iid)
        if not entry: return
        msg, _, _ = entry
        self._store[iid] = (msg, IN_FLIGHT, fut)

    def cancel(self, iid: str, msg: str = None) -> bool:
        """Cancel a message by iid.

        PENDING:    cancel state future, archive immediately.
        IN_FLIGHT:  Task.cancel() on execution future -> CancelledError at next await.
        """
        entry = self._store.get(iid)
        if not entry: return False
        message, status, exec_fut = entry
        if status == PENDING:
            if not message.state.done(): message.state.cancel(msg)
            self._archive(iid, message, CANCELLED)
            return True
        if status == IN_FLIGHT and exec_fut and not exec_fut.done():
            exec_fut.cancel(msg=msg)
            return True
        return False

    def _archive(self, message_id: str, msg: Message, status: int):
        self._store.pop(message_id, None)
        self._history.append((message_id, msg, status))

    def complete(self, message_id: str):
        """Archive message based on its state outcome. Called by Hub after processing."""
        entry = self._store.get(message_id)
        if not entry: return
        msg, _, _ = entry
        if msg.state.cancelled():
            status = CANCELLED
        elif msg.state.done() and msg.state.exception():
            status = FAILED
        else:
            status = DONE
        self._archive(message_id, msg, status)

    @property
    def has_pending(self) -> bool:
        return any(s == PENDING for _, s, _ in self._store.values())

    @property
    def size(self) -> int:
        return len(self._store)
