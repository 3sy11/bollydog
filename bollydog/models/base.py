import asyncio
import inspect
import pathlib
import time
import uuid
from abc import abstractmethod
from typing import Dict, List, Type, Any, ClassVar

import mode
from pydantic import BaseModel, Field, field_serializer, ConfigDict, InstanceOf

from bollydog.service.config import COMMAND_EXPIRE_TIME, HOSTNAME, REPOSITORY_VERSION, DEFAULT_SIGN, DELIVERY_COUNT, DEFAULT_QOS
from bollydog.globals import message


class StreamState(asyncio.Queue):
    def __init__(self):
        super().__init__()
        self._results, self._done_event, self._exception = [], asyncio.Event(), None

    async def put(self, value):
        if value is None: self._done_event.set()
        else: self._results.append(value)
        await super().put(value)

    def set_result(self, result):
        self._results = [result] if not self._results else self._results
        self._done_event.set()

    def set_exception(self, exc):
        self._exception = exc
        self._done_event.set()
        self.put_nowait(None)

    def done(self): return self._done_event.is_set()
    def cancelled(self): return False
    def exception(self): return self._exception
    def result(self):
        if self._exception: raise self._exception
        return self._results[0] if len(self._results) == 1 else self._results

    @property
    def _state(self): return 'FINISHED' if self.done() else 'PENDING'

    def __await__(self):
        async def _wait():
            await self._done_event.wait()
            if self._exception: raise self._exception
            return self.result()
        return _wait().__await__()

    async def __aiter__(self):
        while True:
            value = await self.get()
            if value is None: break
            yield value


class _ModelMixin(BaseModel):
    created_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    update_time: float = Field(default_factory=lambda: int(time.time() * 1000))
    iid: str = Field(default_factory=lambda: uuid.uuid4().hex, max_length=50)
    sign: int = Field(default=DEFAULT_SIGN, description='1:normal, -1:deleted')
    created_by: str = Field(default=None, max_length=50)

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
    qos: int = Field(default=DEFAULT_QOS)
    delivery_count: int = Field(default=DELIVERY_COUNT)
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
    parent_span_id: str = Field(default=getattr(message, 'span_id', '--'))
    data: dict = Field(default_factory=dict)

    def add_event(self, event) -> None:
        self.data.setdefault("events", []).append(event.model_dump() if hasattr(event, 'model_dump') else event)

    def get_event(self, index: int = -1):
        events = self.data.get("events", [])
        return events[index] if events else None

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
        self.state._trace_id = self.trace_id
        # Alternative: root command trace_id = hex(id(state)), intrinsic link
        # if not message: self.trace_id = format(id(self.state), 'x')

    def __init_subclass__(cls, abstract: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if 'module' not in cls.__dict__: cls.module = cls.__module__
        if 'alias' not in cls.__dict__: cls.alias = cls.__name__
        if not abstract and '__call__' in cls.__dict__:
            if 'destination' not in cls.__dict__ or cls.__dict__.get('destination') is None:
                cls.destination = f'_._.{cls.alias}'
            elif len(str(cls.destination).split('.')) <= 2:
                cls.destination = f'{cls.destination}.{cls.alias}'

    def __str__(self):
        _t = 'Event' if isinstance(self, BaseEvent) else 'Command'
        return f'{_t}({self.alias}) dest={self.destination or "-"} trace={self.trace_id[:8]}'

    @abstractmethod
    async def __call__(self, *args, **kwargs) -> Any:
        ...

class BaseEvent(BaseCommand, abstract=True):

    async def __call__(self, *args, **kwargs) -> Any:
        self.state.set_result(True)


class MessageRegistry:
    """Centralized command/event registry, owned by BaseService."""
    def __init__(self):
        self._commands: Dict[str, Type[BaseCommand]] = {}

    def register(self, cmd_cls: Type[BaseCommand]):
        self._commands[f'{cmd_cls.module}.{cmd_cls.alias}'] = cmd_cls

    def resolve(self, name: str) -> Type[BaseCommand]:
        if name in self._commands: return self._commands[name]
        matches = {k: v for k, v in self._commands.items() if k.endswith(f'.{name}')}
        if len(matches) == 1: return next(iter(matches.values()))
        if len(matches) > 1: raise KeyError(f"Ambiguous '{name}': {list(matches.keys())}")
        nl = name.lower()
        matches = {k: v for k, v in self._commands.items() if v.alias.lower() == nl}
        if len(matches) == 1: return next(iter(matches.values()))
        if len(matches) > 1: raise KeyError(f"Ambiguous '{name}': {list(matches.keys())}")
        raise KeyError(f"Command '{name}' not found")

    def topics(self) -> Dict[str, Type[BaseCommand]]:
        return {cmd.destination: cmd for cmd in self._commands.values()}

    def __len__(self): return len(self._commands)
    def __iter__(self): return iter(self._commands)
    def __bool__(self): return bool(self._commands)
    def items(self): return self._commands.items()
    def values(self): return self._commands.values()
    def keys(self): return self._commands.keys()


class BaseService(mode.Service):
    abstract = True
    domain: ClassVar[str]
    alias: ClassVar[str]
    registry: ClassVar[MessageRegistry] = MessageRegistry()
    router_mapping: ClassVar[dict] = {}
    subscriber: ClassVar[dict] = {}
    commands: ClassVar[List[str]] = []
    depends: ClassVar[list] = []

    def __init__(self, **kwargs):
        super().__init__()

    def add_dependency(self, service: 'BaseService') -> 'BaseService':
        super().add_dependency(service)
        return service

    async def on_first_start(self) -> None:
        if False:  # < TODO
            supervisor = mode.OneForOneSupervisor()
            supervisor.add(self)
            await supervisor.start()

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

    def _log_mundane(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log.log(self._mundane_level, msg, stacklevel=3, *args, **kwargs)  # < 3
