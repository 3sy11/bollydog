import asyncio
from typing import Any

from bollydog.models.base import BaseCommand


class TaskCount(BaseCommand):

    async def __call__(self, *args, **kwargs) -> Any:
        return len(asyncio.all_tasks())
