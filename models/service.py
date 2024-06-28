import logging
from typing import List

from core.models.config import ServiceConfig, default_config

from models.base import BaseService
from service.message import MessageManager

logger = logging.getLogger(__name__)


class AppService(BaseService, abstract=True):

    async def on_first_start(self) -> None:
        if self.protocol:
            self.add_dependency(self.protocol.unit_of_work)
        await super(AppService, self).on_first_start()

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()

    def __init__(self, protocol, config: ServiceConfig, handlers: List = None, **kwargs):
        super().__init__()
        self.config = config
        self.protocol = protocol
        self.handlers = handlers or []
        for handler in self.handlers:
            MessageManager.walk_module(handler)

    @classmethod
    def create_from(cls, config: ServiceConfig = default_config, **kwargs):
        if 'protocol' in kwargs:
            config = ServiceConfig(protocol=kwargs.pop('protocol'))
        if 'handlers' in kwargs:
            config.handlers = kwargs.pop('handlers')
        unit_of_work = config.protocol.unit_of_work.module(**config.protocol.unit_of_work.model_dump())
        protocol = config.protocol.module(
            unit_of_work=unit_of_work,
            **config.protocol.model_dump(exclude={'unit_of_work'})  # <
        )
        app_service = cls(
            protocol=protocol,
            config=config,
            **config.model_dump(exclude={'protocol'}),
            **kwargs
        )
        return app_service
