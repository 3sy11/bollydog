import json
from typing import Optional

from bollydog.models.protocol import Protocol


class RedisProtocol(Protocol):

    def __init__(self, url: str = 'redis://localhost', **kwargs):
        self.url = url
        super().__init__(**kwargs)

    def create(self):
        import aioredis
        return aioredis.from_url(self.url)

    async def get(self, key: str) -> Optional[dict]:
        data = await self.adapter.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value, ttl: int = 3600):
        await self.adapter.set(key, json.dumps(value), ex=ttl)

    async def remove(self, key: str):
        await self.adapter.delete(key)

    def delete(self):
        pass
