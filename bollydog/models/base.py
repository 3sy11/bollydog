import asyncio
import time
import uuid
from abc import abstractmethod
from typing import Dict, List, Type, Any, ClassVar

from pydantic import BaseModel, Field, field_serializer, ConfigDict, InstanceOf

from bollydog.service.config import COMMAND_EXPIRE_TIME, HOSTNAME, REPOSITORY_VERSION, DEFAULT_SIGN, DELIVERY_COUNT, DEFAULT_QOS
from bollydog.globals import message, session


class _ModelMixin(BaseModel):
    created_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    update_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    iid: str = Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    sign: int = Field(default=DEFAULT_SIGN, description='1:normal, -1:deleted')
    created_by: str = Field(default=None, max_length=50)

    def model_post_init(self, __context: Any) -> None:
        self.created_by = getattr(session, 'username', None) or HOSTNAME


class BaseDomain(_ModelMixin):
    """BaseDomain is the base class for DDD."""
    model_config = ConfigDict(extra='ignore')


class BaseCommand(_ModelMixin):
    model_config = ConfigDict(extra='allow')
    _registry: ClassVar[Dict[str, Type['BaseCommand']]] = {}
    host: ClassVar[str] = HOSTNAME
    version: ClassVar[str] = REPOSITORY_VERSION
    module: ClassVar[str]
    alias: ClassVar[str]
    destination: ClassVar[str] = None

    # instance
    expire_time: float = Field(default=COMMAND_EXPIRE_TIME)
    qos: int = Field(default=DEFAULT_QOS)
    delivery_count: int = Field(default=DELIVERY_COUNT)
    state: InstanceOf[asyncio.Future] = Field(default_factory=asyncio.Future)

    @field_serializer('state')
    def serialize_state(self, state: asyncio.Future, _info) -> List:
        _result = None
        if state.done():
            if not state.cancelled():
                if state.exception():
                    _result = str(state.exception())
                else:
                    _result = state.result()
            else:
                _result = state._cancel_message  # noqa
        return [state._state, _result]  # noqa

    # trace
    trace_id: str = Field(default_factory=lambda: getattr(message, 'trace_id', uuid.uuid4().hex))
    span_id: str = Field(default='--')
    parent_span_id: str = Field(default=getattr(message, 'span_id', '--'))

    # # data
    # data: dict = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.span_id = self.span_id if self.span_id != '--' else self.iid
        # self.data['model_fields_set'] = list(self.model_fields_set)
        # self.data['model_extra'] = self.model_extra
        if message:
            self.trace_id = message.trace_id
            self.parent_span_id = message.span_id

    def __init_subclass__(cls, abstract: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if 'module' not in cls.__dict__:
            cls.module = cls.__module__
        if 'alias' not in cls.__dict__:
            cls.alias = cls.__name__.lower()
        if not abstract and '__call__' in cls.__dict__:
            cls._registry[f'{cls.module}.{cls.alias}'] = cls

    @classmethod
    def resolve(cls, name: str) -> Type['BaseCommand']:
        if name in cls._registry:
            return cls._registry[name]
        matches = {k: v for k, v in cls._registry.items() if k.endswith(f'.{name}')}
        if len(matches) == 1:
            return next(iter(matches.values()))
        if len(matches) > 1:
            raise KeyError(f"Ambiguous alias '{name}', candidates: {list(matches.keys())}")
        raise KeyError(f"Command '{name}' not found")

    @abstractmethod
    async def __call__(self, *args, **kwargs) -> Any:
        ...

class BaseEvent(BaseCommand, abstract=True):
    
    qos: ClassVar[int] = not DEFAULT_QOS

    async def __call__(self, *args, **kwargs) -> Any:
        self.state.set_result(True)
