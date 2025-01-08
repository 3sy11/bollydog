import asyncio
import inspect
import pathlib
import time
import uuid
from functools import lru_cache
from typing import Dict, Type, List, Any, ClassVar

import mode
from pydantic import BaseModel, Field, field_serializer, ConfigDict, InstanceOf
from pydantic_core import PydanticUndefined
from typing_extensions import Annotated

from bollydog.config import MESSAGE_EXPIRE_TIME, HOSTNAME, REPOSITORY_VERSION
from bollydog.globals import message, session

_DEFAULT_SIGN = 1
_DELIVERY_COUNT = 0
_DEFAULT_QOS = 1
# ModulePathWithDot = Annotated[str, lambda path: smart_import(path)]
ModulePathWithDot = Annotated[str, lambda path: '.' in path]
MessageName = Annotated[str, 'MessageName']
MessageId = Annotated[str, 'MessageId']
MessageTraceId = Annotated[str, 'MessageTraceId']
DomainName = Annotated[str, 'Domain']


@lru_cache  # ?
def get_model_name(o) -> str:
    if inspect.isfunction(o):
        return f'{o.__module__}.{o.__name__}'
    elif issubclass(o, BaseModel):
        if 'name' in o.model_fields \
                and o.model_fields['name'].default \
                and o.model_fields['name'].default != PydanticUndefined:
            return o.model_fields['name'].default
        else:
            return f'{o.__module__}.{o.__name__}'
    else:
        return f'{o.__module__}.{o.__name__}'


def get_class_domain(cls: Type) -> str:
    return inspect.getfile(cls).split('/')[-2]


class _ModelMixin(BaseModel):
    created_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    update_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    iid: str = Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    sign: int = Field(default=_DEFAULT_SIGN)
    created_by: str = Field(default_factory=lambda :getattr(session,'username',HOSTNAME), max_length=50)


Domains: Dict[DomainName, Type['BaseDomain']] = {}


class BaseDomain(_ModelMixin):
    model_config = ConfigDict(extra='ignore')

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        Domains[get_model_name(cls)] = cls


class BaseMessage(_ModelMixin):
    model_config = ConfigDict(extra='allow')

    # # system
    host: ClassVar[str] = HOSTNAME
    version: ClassVar[str] = REPOSITORY_VERSION
    module: ClassVar[str]
    domain: ClassVar[DomainName]
    name: ClassVar[MessageName]
    expire_time: ClassVar[float] = MESSAGE_EXPIRE_TIME
    # destination: str = Field(default=None)  # <

    # # state
    handlers: List[ModulePathWithDot] = Field(default_factory=list)
    delivery_count: ClassVar[int] = _DELIVERY_COUNT
    state: InstanceOf[asyncio.Future] = Field(default_factory=asyncio.Future)
    qos: ClassVar[int] = _DEFAULT_QOS

    # conditions: Dict = Field(default=None)  # <

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
                _result = state._cancel_message  # # noqa
        return [state._state, _result]  # # noqa

    # # trace
    trace_id: str = Field(default_factory=lambda: getattr(message, 'trace_id', uuid.uuid4().hex))
    span_id: str = Field(default='--')
    parent_span_id: str = Field(default=getattr(message, 'span_id', '--'))

    # # data
    data: dict = Field(default_factory=dict)

    # subject: str = Field(default=None)  # <
    # schema: str = Field(default=None)  # <
    # schema_version: str = Field(default='0')  # <

    def model_post_init(self, __context: Any) -> None:
        # self.state = asyncio.Future()
        self.span_id = self.span_id if self.span_id != '--' else self.iid
        self.data['model_fields_set'] = list(self.model_fields_set)  # # `set` type not satisfy database
        self.data['model_extra'] = self.model_extra
        if message:
            # self.state = message.state
            self.trace_id = message.trace_id
            self.parent_span_id = message.span_id

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        cls.name = cls.__name__.lower()
        cls.module = cls.__module__


class Command(BaseMessage):

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)


class Event(BaseMessage):
    ...


class BaseService(mode.Service):
    abstract = True
    domain: DomainName = None
    name: str = None
    path: pathlib.Path

    def __init__(self, domain, name=None, *args, **kwargs):
        super().__init__()
        self.domain = domain or self.domain
        self.name = name or self.name or self.__class__.__name__.lower()
        self.name = f'{self.domain}.{self.name}'

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        service.name = f'{self.name}.{service.name}'
        super().add_dependency(service)
        return service

    async def on_first_start(self) -> None:
        supervisor = mode.OneForOneSupervisor()
        supervisor.add(self)
        await supervisor.start()

    async def crash(self, reason: BaseException) -> None:
        self.logger.error(reason)
        await super(BaseService, self).crash(reason)

    def __init_subclass__(cls, abstract=False, **kwargs):
        super(BaseService, cls).__init_subclass__()
        cls.path = pathlib.Path(inspect.getmodule(cls).__file__).parent

    def __repr__(self) -> str:
        return f"<{self._repr_name()}: {self.state}: {id(self)}>"

    def _log_mundane(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log.log(self._mundane_level, msg, stacklevel=3, *args, **kwargs)  # < 3


class Session(BaseModel):
    uid: str = Field(default_factory=lambda: uuid.uuid4().hex)
    username: str = Field(default=HOSTNAME)
    collection: dict = Field(default_factory=dict)
