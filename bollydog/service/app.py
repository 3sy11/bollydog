import asyncio
from typing import Iterable

import mode

from bollydog.exception import ServiceRejectException, HandlerTimeOutError, HandlerMaxRetryError
from bollydog.globals import _hub_ctx_stack, _protocol_ctx_stack, _message_ctx_stack, _app_ctx_stack, _session_ctx_stack
from bollydog.models.base import BaseCommand as Message
from bollydog.models.service import AppService
from bollydog.service.router import Router
from bollydog.service.session import Session
from bollydog.service.broker import Broker
from bollydog.service.config import DOMAIN


class Hub(AppService):
    domain = DOMAIN
    router_mapping = {'TaskCount': ['GET', '/api/ping']}
    apps: dict
    router: Router
    session: Session
    broker: Broker

    def __init__(self, apps: Iterable[AppService] = None, **kwargs):
        super().__init__(**kwargs)
        self.router = Router()
        self.session = Session()
        self.broker = Broker()
        self.add_dependency(self.router)
        self.add_dependency(self.session)
        self.add_dependency(self.broker)
        _id = lambda s: f'{s.domain}.{s.alias}'
        self.apps = {_id(self): self, _id(self.router): self.router, _id(self.session): self.session, _id(self.broker): self.broker}
        for app in apps or []:
            self.add_service(app)
        self.exit_stack.enter_context(_hub_ctx_stack.push(self))

    async def on_started(self) -> None:
        for service in self.apps.values():
            if service == self:
                continue
            await service.maybe_start()
        self.logger.info(self.apps)

    def add_service(self, service: AppService):
        key = f'{service.domain}.{service.alias}'
        assert key not in self.apps
        self.apps[key] = service

    async def put_message(self, message: Message) -> Message:
        if self.should_stop:
            raise ServiceRejectException()
        msg = await self.broker.put(message)
        self.logger.info(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias}')
        return msg

    async def dispatch(self, message: Message) -> Message:
        if message.qos == 0 and self.state == "running":
            return await self.put_message(message)
        return await self.execute(message)

    @mode.Service.task
    async def run(self):
        while not self.should_stop or self.broker.size > 0:
            message = await self.broker.take()
            if not message:
                continue
            self.logger.debug(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias} {message.model_dump()}')
            self.logger.info(f'{message.trace_id[:2]}{message.parent_span_id[:2]}:{message.span_id[:2]} {message.alias}')
            asyncio.create_task(self._process_message(message))

    async def _process_message(self, message: Message):
        try:
            await self.execute(message)
            await self.router.publish(message)
        except Exception as e:
            self.logger.error(f'process message error: {e}')
            self.logger.exception(e)

    def _resolve_app(self, message: Message):
        if not message.destination:
            return None
        return self.apps.get(message.destination)

    async def _iterate(self, message: Message, gen):
        feedback, pending = None, []
        try:
            while True:
                value = pending.pop() if pending else await asyncio.wait_for(gen.asend(feedback), timeout=message.expire_time)
                if isinstance(value, Message):
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
                    yield value
        except StopAsyncIteration:
            pass

    async def _execute(self, message: Message):
        while not message.state.done() and not message.state.cancelled():
            try:
                coro = message()
                if message.is_async_gen:
                    async for value in self._iterate(message, coro):
                        await message.state.put(value)
                    await message.state.put(None)
                    result = message.state.result()
                else:
                    result = await asyncio.wait_for(coro, timeout=message.expire_time)
                    message.state.set_result(result)
                self.broker.ack(message.iid, result)
            except (TimeoutError, HandlerTimeOutError, HandlerMaxRetryError) as e:
                if message.delivery_count:
                    self.logger.info(f'{message.alias} retrying {message.delivery_count}')
                    message.delivery_count -= 1
                    continue
                message.state.set_exception(e)
                self.broker.nack(message.iid, e)
            except Exception as e:
                self.logger.exception(e)
                message.state.set_exception(e)
                self.broker.nack(message.iid, e)
            break

    async def execute(self, message: Message) -> Message:
        app = self._resolve_app(message)
        ctx = await self.session.acquire(message)
        try:
            with (_protocol_ctx_stack.push(app.protocol if app else None), _message_ctx_stack.push(message), _app_ctx_stack.push(app), _session_ctx_stack.push(ctx)):
                await self._execute(message)
        except Exception as e:
            self.logger.error(f'{e}')
            if not message.state.done(): message.state.set_exception(e)
        finally:
            await self.session.release(message)
        return message
