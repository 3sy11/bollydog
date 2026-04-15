import asyncio
from contextlib import asynccontextmanager
from typing import Iterable

import mode

from bollydog.exception import HandlerTimeOutError, HandlerMaxRetryError, DestinationNotFoundError, ServiceNotFoundError
from bollydog.globals import _hub_ctx_stack, _protocol_ctx_stack, _message_ctx_stack, _app_ctx_stack, _session_ctx_stack
from bollydog.models.base import BaseCommand as Message, BaseEvent
from bollydog.models.service import AppService
from bollydog.service.exchange import Exchange
from bollydog.service.session import Session
from bollydog.service.queue import Queue
from bollydog.service.config import DOMAIN, HUB_ROUTER_MAPPING


class Hub(AppService):
    """
    Pipeline overview (dispatch routing + execution paths):

    ```mermaid
    flowchart TB
        subgraph dispatch_routing [dispatch routing]
            isEvent{"isinstance BaseEvent?"}
            isQos1{"qos == 1?"}
        end
        subgraph fire_path ["_fire(msg)"]
            ctx1["async with _with_context(msg)"]
            run1["await _run or _run_gen"]
            elev1["await _publish(msg)"]
            ctx1 --> run1 --> elev1
        end
        subgraph queue_path ["_process_queued(msg)"]
            ctx2["async with _with_context(msg)"]
            run2["await _run or _run_gen"]
            ack2["ack / nack"]
            elev2["await _publish(msg)"]
            ctx2 --> run2 --> ack2 --> elev2
        end
        subgraph cli_path ["execute(msg)"]
            ctx3["async with _with_context(msg)"]
            run3["await _run or _run_gen"]
            ctx3 --> run3
        end

        disp[dispatch] --> isEvent
        isEvent -->|Yes| ct1["create_task(_fire)"]
        isEvent -->|No| isQos1
        isQos1 -->|No| ct2["create_task(_fire)"]
        isQos1 -->|Yes| qput["queue.put"]
        qput --> consumer["consumer: create_task(_process_queued)"]
        ct1 --> fire_path
        ct2 --> fire_path
        consumer --> queue_path
        exec_cli[execute] --> cli_path
    ```

    Key: Event and Command qos=0 share `_fire(msg)`; no separate `_dispatch_event`.
    """
    domain = DOMAIN
    router_mapping = HUB_ROUTER_MAPPING
    commands = ['commands']
    apps: dict
    exchange: Exchange
    session: Session
    queue: Queue

    def __init__(self, apps: Iterable[AppService] = None, **kwargs):
        super().__init__(**kwargs)
        self._load_commands(self.commands)
        self._before, self._after = [], []
        self.exchange = Exchange()
        self.exchange._hub = self
        self.session = Session()
        self.queue = Queue()
        self.add_dependency(self.exchange)
        self.add_dependency(self.session)
        self.add_dependency(self.queue)
        _id = lambda s: f'{s.domain}.{s.alias}'
        self.apps = {_id(self): self, _id(self.exchange): self.exchange, _id(self.session): self.session, _id(self.queue): self.queue}
        for app in apps or []:
            self.add_service(app)
        self.exit_stack.enter_context(_hub_ctx_stack.push(self))
        self.exit_stack.enter_context(_session_ctx_stack.push(self.session))

    async def on_started(self) -> None:
        for service in self.apps.values():
            if service == self: continue
            await service.maybe_start()
        for sid, svc in self.apps.items():
            cmds = getattr(svc, 'commands', None)
            if cmds: self.logger.info(f'[{sid}] {type(svc).__name__} | commands={cmds}')
        if Message._registry:
            def _tag(c): return 'Event' if issubclass(c, BaseEvent) else 'Command'
            reg = '\n  '.join(f'{_tag(c):7} {c.alias:20} dest={c.destination or "-"}' for c in Message._registry.values())
            self.logger.info(f'registry({len(Message._registry)}):\n  {reg}')

    async def emit(self, event: Message, topic: str = None):
        await self.dispatch(event)

    def add_service(self, service: AppService):
        key = f'{service.domain}.{service.alias}'
        if key in self.apps: return
        self.apps[key] = service
        for child in getattr(service, '_children', []):
            if isinstance(child, AppService):
                self.add_service(child)

    def get_service(self, cls_or_key, *, required=True):
        if isinstance(cls_or_key, str):
            key = cls_or_key
        elif isinstance(cls_or_key, type):
            key = f'{cls_or_key.domain}.{cls_or_key.alias}'
        else:
            key = f'{type(cls_or_key).domain}.{type(cls_or_key).alias}'
        svc = self.apps.get(key)
        if svc is None and required:
            raise ServiceNotFoundError(f"Service '{key}' not registered")
        return svc

    def before(self, fn):
        self._before.append(fn); return fn

    def after(self, fn):
        self._after.append(fn); return fn

    async def gather(self, commands: list) -> list:
        subs = [await self.dispatch(cmd) for cmd in commands]
        return await asyncio.gather(*(sub.state for sub in subs), return_exceptions=True)

    async def dispatch(self, message: Message) -> Message:
        if isinstance(message, BaseEvent):
            asyncio.create_task(self._fire(message))
        elif message.qos == 1:
            await self.queue.put(message)
        else:
            asyncio.create_task(self._fire(message))
        return message

    async def execute(self, message: Message) -> Message:
        runner = self._run_gen if message.is_async_gen else self._run
        async with self._with_context(message):
            await self._execute(message, runner)
        return message

    async def _execute(self, message, runner):
        for fn in self._before:
            short = await fn(message)
            if short is not None:
                if not message.state.done(): message.state.set_result(short)
                return
        await runner(message)
        exc = message.state.exception() if message.state.done() else None
        result = message.state.result() if message.state.done() and not exc else None
        for fn in reversed(self._after):
            await fn(message, result=result, exception=exc)

    @asynccontextmanager
    async def _with_context(self, message):
        app = self._resolve_app(message)
        with (_protocol_ctx_stack.push(app.protocol if app else None), _message_ctx_stack.push(message), _app_ctx_stack.push(app)):
            yield

    async def _fire(self, message):
        runner = self._run_gen if message.is_async_gen else self._run
        async with self._with_context(message):
            await self._execute(message, runner)
            await self._publish(message)

    async def _publish(self, message):
        topic = type(message).destination
        if not topic: return
        if message.state.done() and (message.state.cancelled() or message.state.exception()): return
        for handler in self.exchange.match(topic):
            cmd = handler()
            cmd.add_event(message)
            await self.dispatch(cmd)

    async def _run(self, message):
        while True:
            try:
                result = await asyncio.wait_for(message(), timeout=message.expire_time)
                if isinstance(result, Message):  # handoff: chain depth > 5 may degrade perf (stack frames retained)
                    result.trace_id = message.trace_id
                    result.data = {**message.data, **result.data}
                    self.logger.info(f'handoff {message.alias} -> {result.alias}')
                    sub = await self.dispatch(result)
                    result = await sub.state
                if not message.state.done(): message.state.set_result(result)
                break
            except (TimeoutError, HandlerTimeOutError, HandlerMaxRetryError) as e:
                if message.delivery_count:
                    self.logger.info(f'{message.alias} retrying {message.delivery_count}')
                    message.delivery_count -= 1; continue
                if not message.state.done(): message.state.set_exception(e)
                break
            except Exception as e:
                self.logger.exception(e)
                if not message.state.done(): message.state.set_exception(e)
                break

    async def _run_gen(self, message):
        gen = message()
        feedback, pending = None, []
        try:
            while True:
                value = pending.pop() if pending else await asyncio.wait_for(gen.asend(feedback), timeout=message.expire_time)
                if isinstance(value, (list, tuple)):
                    subs = [await self.dispatch(cmd) for cmd in value]
                    feedback = await asyncio.gather(*(sub.state for sub in subs), return_exceptions=True)
                elif isinstance(value, Message):
                    sub = await self.dispatch(value)
                    try:
                        feedback = await sub.state
                    except Exception as exc:
                        try:
                            pending.append(await asyncio.wait_for(gen.athrow(exc), timeout=message.expire_time))
                            feedback = None
                        except StopAsyncIteration:
                            return
                else:
                    feedback = None
                    await message.state.put(value)
        except StopAsyncIteration:
            pass
        except Exception as e:
            self.logger.exception(e)
            if not message.state.done(): message.state.set_exception(e)
            return
        await message.state.put(None)

    @mode.Service.task
    async def run(self):
        while not self.should_stop or self.queue.size > 0:
            message = await self.queue.take()
            if not message: continue
            self.logger.info(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias}')
            asyncio.create_task(self._process_queued(message))

    async def _process_queued(self, message):
        runner = self._run_gen if message.is_async_gen else self._run
        async with self._with_context(message):
            await self._execute(message, runner)
            if message.state.done() and not message.state.exception():
                self.queue.ack(message.iid, message.state.result())
            else:
                self.queue.nack(message.iid, message.state.exception())
            await self._publish(message)

    def _resolve_app(self, message: Message):
        dest = type(message).destination
        if not dest: return None
        parts = dest.split('.')
        service_key = '.'.join(parts[:2])
        if service_key == '_._': return None
        svc = self.apps.get(service_key)
        if svc is None:
            raise DestinationNotFoundError(f"Service '{service_key}' not found for {type(message).__name__}")
        return svc
