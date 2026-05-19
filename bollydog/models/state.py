import asyncio
import contextvars


class StreamState(asyncio.Queue):
    """Streaming state for async generator Commands.
    Duck-types asyncio.Future: add_done_callback strictly mirrors Future's context-capture behavior."""

    def __init__(self):
        super().__init__()
        self._results, self._done_event, self._exception = [], asyncio.Event(), None
        self._done_callbacks = []

    def add_done_callback(self, callback):
        if self.done():
            asyncio.get_event_loop().call_soon(callback, self)
        else:
            self._done_callbacks.append((callback, contextvars.copy_context()))

    def _schedule_callbacks(self):
        for callback, context in self._done_callbacks:
            asyncio.get_event_loop().call_soon(callback, self, context=context)
        self._done_callbacks.clear()

    async def put(self, value):
        if value is None:
            self._done_event.set()
            self._schedule_callbacks()
        else:
            self._results.append(value)
        await super().put(value)

    def set_result(self, result):
        self._results = [result] if not self._results else self._results
        self._done_event.set()
        self._schedule_callbacks()

    def set_exception(self, exc):
        self._exception = exc
        self._done_event.set()
        self.put_nowait(None)
        self._schedule_callbacks()

    def done(self): return self._done_event.is_set()
    def cancelled(self): return False
    def exception(self): return self._exception
    def result(self):
        if self._exception: raise self._exception
        return self._results[0] if len(self._results) == 1 else self._results

    @property
    def _state(self): return 'FINISHED' if self.done() else 'PENDING'

    def __await__(self):
        async def _wait():
            await self._done_event.wait()
            if self._exception: raise self._exception
            return self.result()
        return _wait().__await__()

    async def __aiter__(self):
        while True:
            value = await self.get()
            if value is None: break
            yield value
