import asyncio
import inspect
import pathlib
import time
import uuid
from abc import abstractmethod
from typing import Dict, List, Optional, Type, Any, ClassVar

import mode
from pydantic import BaseModel, Field, field_serializer, ConfigDict, InstanceOf

import os
from bollydog.utils.base import get_hostname, get_repository_version
from bollydog.globals import message

HOSTNAME = get_hostname()
REPOSITORY_VERSION = get_repository_version()
COMMAND_EXPIRE_TIME = int(os.getenv('COMMAND_EXPIRE_TIME', 3600))
COMMAND_DEFAULT_SIGN = int(os.getenv('COMMAND_DEFAULT_SIGN', 1))
COMMAND_DELIVERY_COUNT = int(os.getenv('COMMAND_DELIVERY_COUNT', 0))


from bollydog.models.state import StreamState  # noqa: E402


class _ModelMixin(BaseModel):
    created_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    update_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    iid: str = Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    sign: int = Field(default=COMMAND_DEFAULT_SIGN, description='1:normal, -1:deleted')
    created_by: Optional[str] = Field(default=None, max_length=50)

    def model_post_init(self, __context: Any) -> None:
        if self.created_by is None:
            self.created_by = HOSTNAME


class BaseDomain(_ModelMixin):
    """BaseDomain is the base class for DDD."""
    model_config = ConfigDict(extra='ignore')


class BaseCommand(_ModelMixin):
    model_config = ConfigDict(extra='allow')
    host: ClassVar[str] = HOSTNAME
    version: ClassVar[str] = REPOSITORY_VERSION
    module: ClassVar[str]
    alias: ClassVar[str]
    destination: ClassVar[str] = None

    expire_time: float = Field(default=COMMAND_EXPIRE_TIME)
    # qos: int — removed. All messages go through Queue uniformly.
    delivery_count: int = Field(default=COMMAND_DELIVERY_COUNT)
    state: InstanceOf[asyncio.Future] = Field(default_factory=asyncio.Future)

    @field_serializer('state')
    def serialize_state(self, state: asyncio.Future, _info) -> List:
        _result = None
        if state.done():
            if not state.cancelled():
                _result = str(state.exception()) if state.exception() else state.result()
            else:
                _result = state._cancel_message  # noqa
        return [state._state, _result]  # noqa

    trace_id: str = Field(default_factory=lambda: getattr(message, 'trace_id', uuid.uuid4().hex))
    span_id: str = Field(default='--')
    parent_span_id: str = Field(default='--')
    data: dict = Field(default_factory=dict)

    @property
    def is_async_gen(self) -> bool:
        return inspect.isasyncgenfunction(type(self).__call__)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.is_async_gen: self.state = StreamState()
        self.span_id = self.span_id if self.span_id != '--' else self.iid
        if message:
            self.trace_id = message.trace_id
            self.parent_span_id = message.span_id

    def __init_subclass__(cls, abstract: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if 'module' not in cls.__dict__: cls.module = cls.__module__
        if 'alias' not in cls.__dict__: cls.alias = cls.__name__
        if not abstract and '__call__' in cls.__dict__:
            if 'destination' not in cls.__dict__ or cls.__dict__.get('destination') is None:
                cls.destination = f'_._.{cls.alias}'  # placeholder, rebound by _derive in _load_commands

    @classmethod
    def _derive(cls, dest_prefix: str):
        """Create derived subclass with isolated destination. Original class unchanged."""
        return type(cls.__name__, (cls,), {'destination': f'{dest_prefix}.{cls.alias}', 'module': cls.module, 'alias': cls.alias})

    def __str__(self):
        _t = 'Event' if isinstance(self, BaseEvent) else 'Command'
        return f'{_t}({self.alias}) dest={self.destination or "-"} trace={self.trace_id[:8]}'

    @abstractmethod
    async def __call__(self, *args, **kwargs) -> Any:
        ...

class BaseEvent(BaseCommand, abstract=True):

    async def __call__(self, *args, **kwargs) -> Any:
        self.state.set_result(True)


class BaseService(mode.Service):
    abstract = True
    domain: ClassVar[str]
    alias: ClassVar[str]
    registry: ClassVar[Dict[str, Type[BaseCommand]]] = {}
    router_mapping: ClassVar[dict] = {}
    subscriber: ClassVar[dict] = {}
    commands: ClassVar[List[str]] = []
    depends: ClassVar[dict] = {}

    def dep(self, key: str) -> 'BaseService':
        """Get declared dependency by domain.alias key. Raises ValueError if not found."""
        svc = self.depends.get(key)
        if svc is None: raise ValueError(f'{self.domain}.{self.alias} has no dependency: {key}')
        return svc

    def __init__(self, **kwargs):
        super().__init__()

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        super().add_dependency(service)
        return service

    async def crash(self, reason: BaseException) -> None:
        self.logger.error(reason)
        await super(BaseService, self).crash(reason)

    def __init_subclass__(cls, abstract=False, **kwargs):
        super(BaseService, cls).__init_subclass__()
        if 'domain' not in cls.__dict__:
            cls.domain = pathlib.Path(inspect.getmodule(cls).__file__).parent.name
        if 'alias' not in cls.__dict__:
            cls.alias = cls.__name__

    def __repr__(self) -> str:
        return f"<{self._repr_name()}: {self.state}: {id(self)}>"
