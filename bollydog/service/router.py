from typing import Callable, Dict, Set

from bollydog.models.service import AppService
from bollydog.models.base import BaseCommand as Message
from bollydog.service.config import DOMAIN


class Router(AppService):
    domain = DOMAIN
    callbacks: Dict[str, Set[Callable]] = {'*': set()}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def route(self, message: Message):
        self.production(message)
        self.logger.info(f'{message.trace_id}|\001\001|{message.mid} from {message.parent_span_id or "0"}')

    def production(self, message: Message):
        ...

    def register(self, name: str, callback: Callable):  # < 绑定消息名称
        if name not in self.callbacks:
            self.callbacks[name] = {callback, }
        else:
            self.callbacks[name].add(callback)

    def unregister(self, name: str, callback: Callable):
        if name in self.callbacks and callback in self.callbacks[name]:
            self.callbacks[name].remove(callback)
        else:
            self.logger.warning(f'{callback} not in {name}')

    async def publish(self, message: Message):
        if message.alias in self.callbacks:
            for callback in self.callbacks[message.alias]:
                await callback(message)
        for callback in self.callbacks['*']:
            await callback(message)
        self.logger.debug(f'{message.iid} from {message.parent_span_id or "0"}')
