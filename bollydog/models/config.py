from typing import Type, List, Any

from bollydog.adapters.local import NoneProtocol, NoneUnitOfWork
from bollydog.models.protocol import Protocol, UnitOfWork
from pydantic import BaseModel, Field, ConfigDict, AnyUrl

from bollydog.models.base import BaseMessage, ModulePathWithDot


class UnitOfWorkConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    module: Type[UnitOfWork] = Field(default=None)
    adapter: Any = Field(default=None)


class ProtocolConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    module: Type[Protocol] = Field(default=None)
    events: List[BaseMessage] = Field(default_factory=list)
    unit_of_work: UnitOfWorkConfig = Field(default_factory=lambda: UnitOfWorkConfig(module=NoneUnitOfWork))


class ServiceConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    handlers: List[ModulePathWithDot] = Field(default_factory=list)
    protocol: ProtocolConfig = Field(default_factory=lambda: ProtocolConfig(module=NoneProtocol))


default_config = ServiceConfig()
