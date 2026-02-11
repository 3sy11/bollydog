from bollydog.models.base import BaseCommand
import asyncio
from typing import Any


class TaskCount(BaseCommand):
    
    async def __call__(self, *args, **kwargs) -> Any:
        return len(asyncio.all_tasks())