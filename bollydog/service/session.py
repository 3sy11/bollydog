from bollydog.models.service import BaseService
from bollydog.adapters.memory import MemoryProtocol
from bollydog.service.config import DOMAIN


class Session(BaseService):
    domain = DOMAIN
    protocol = None

    def on_init_dependencies(self):
        if self.protocol is None: self.protocol = MemoryProtocol()
        return [self.protocol]

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
