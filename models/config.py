from typing import Type, List, Any

from core.adapters.other import NoneProtocol, NoneUnitOfWork
from core.models.protocol import Protocol, UnitOfWork
from pydantic import BaseModel, Field, ConfigDict, AnyUrl

from models.base import BaseMessage, ModulePathWithDot


class UnitOfWorkConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    module: Type[UnitOfWork] = Field(default=None)
    url: AnyUrl = Field(default=None)
    engine: Any = Field(default=None)


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
