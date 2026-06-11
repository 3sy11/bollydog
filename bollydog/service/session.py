from bollydog.config import DOMAIN
from bollydog.models.service import AppService


class Session(AppService):
    domain = DOMAIN
    protocol = None

    async def get(self, key) -> dict:
        return await self.protocol.get(key) or {}

    async def set(self, key, data: dict):
        await self.protocol.set(key, data)

    async def delete(self, key):
        await self.protocol.remove(key)

    async def append(self, key, field, value):
        data = await self.get(key)
        data.setdefault(field, []).append(value)
        await self.set(key, data)

    async def history(self, key, field='turns', last_n=None) -> list:
        data = await self.get(key)
        items = data.get(field, [])
        return items[-last_n:] if last_n else items
