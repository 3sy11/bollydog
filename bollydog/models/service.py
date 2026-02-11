import logging

from bollydog.models.base import BaseService

logger = logging.getLogger(__name__)


class AppService(BaseService, abstract=True):

    async def on_first_start(self) -> None:
        await super(AppService, self).on_first_start()

    async def on_start(self) -> None:
        await super(AppService, self).on_start()

    async def on_started(self) -> None:
        await super(AppService, self).on_started()

    def __init__(self, protocol=None, **kwargs):
        super().__init__(**kwargs)
        self.protocol = protocol

    @classmethod
    def create_from(cls, domain, protocol=None, **kwargs):
        logger.debug(f'create_from {cls.__name__} {domain} {protocol}')
        if protocol:
            protocol = protocol['module'](domain=domain, **protocol)
        app_service = cls(domain=domain, protocol=protocol, **kwargs)
        if protocol:
            app_service.add_dependency(protocol)
        return app_service
