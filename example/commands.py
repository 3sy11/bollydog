import asyncio
from typing import Any
from bollydog.models.base import BaseCommand


class Ping(BaseCommand):
    """Simple health-check command."""

    async def __call__(self, *args, **kwargs) -> Any:
        return {'pong': True, 'tasks': len(asyncio.all_tasks())}


class Echo(BaseCommand):
    """Echoes user input back."""
    text: str = 'hello bollydog'

    async def __call__(self, *args, **kwargs) -> Any:
        return {'echo': self.text}


class Countdown(BaseCommand):
    """Streaming command — yields a countdown sequence via SSE."""
    n: int = 5

    async def __call__(self, *args, **kwargs):
        for i in range(self.n, 0, -1):
            await asyncio.sleep(0.5)
            yield {'count': i}
        yield {'count': 0, 'done': True}


class Pipeline(BaseCommand):
    """Orchestration demo — yields sub-commands and collects results."""

    async def __call__(self, *args, **kwargs):
        ping_result = yield Ping()
        echo_result = yield Echo(text=f'tasks={ping_result["tasks"]}')
        yield {'ping': ping_result, 'echo': echo_result}
