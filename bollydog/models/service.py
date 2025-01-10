import logging
from typing import List

from bollydog.models.base import BaseService
from bollydog.service.handler import AppHandler

logger = logging.getLogger(__name__)


class AppService(BaseService, abstract=True):

    async def on_first_start(self) -> None:
        await super(AppService, self).on_first_start()

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()

    def __init__(self, protocol=None, handlers: List = None, **kwargs):
        super().__init__(**kwargs)
        self.protocol = protocol
        self.handlers = handlers or []

    @classmethod
    def create_from(cls, domain, unit_of_work=None, protocol=None, handlers=None, **kwargs):
        assert (unit_of_work is None) == (protocol is None)
        if unit_of_work:
            unit_of_work = unit_of_work['module'](domain=domain, **unit_of_work)
            protocol = protocol['module'](unit_of_work=unit_of_work, **protocol)
        app_service = cls(domain=domain, protocol=protocol, **kwargs)
        if protocol:
            app_service.add_dependency(unit_of_work)
        for handler in handlers or []:
            AppHandler.walk_module(handler, app_service)
        return app_service
