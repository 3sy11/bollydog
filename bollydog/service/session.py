from pydantic import BaseModel, Field

from bollydog.models.service import BaseService
from bollydog.adapters.local import MemoryProtocol
from bollydog.service.config import DOMAIN, HOSTNAME


class SessionContext(BaseModel):
    trace_id: str
    username: str = HOSTNAME
    collection: dict = Field(default_factory=dict)


class Session(BaseService):
    domain = DOMAIN

    def __init__(self, protocol=None, **kwargs):
        super().__init__(**kwargs)
        self.protocol = protocol or MemoryProtocol()

    async def acquire(self, message, **kwargs) -> SessionContext:
        key = message.trace_id
        data = await self.protocol.get(key)
        if data:
            return SessionContext.model_validate(data)
        ctx = SessionContext(trace_id=message.trace_id, **kwargs)
        await self.protocol.set(key, ctx.model_dump())
        return ctx

    async def release(self, message):
        await self.protocol.remove(message.trace_id)

    async def save(self, message, ctx: SessionContext):
        await self.protocol.set(message.trace_id, ctx.model_dump())
