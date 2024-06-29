import os

from bollydog.adapters.other import NoneProtocol, NoneUnitOfWork
from bollydog.models.config import default_config, ProtocolConfig, UnitOfWorkConfig
from mode.utils.imports import smart_import

HANDLERS = os.getenv('BOLLYDOG_HANDLERS', ['core.service.handler', ])
QUEUE_MAX_SIZE = 1000
PROTOCOL = os.getenv('BOLLYDOG_BUS_SERVICE_PROTOCOL', None)
PROTOCOL = NoneProtocol if PROTOCOL is None else smart_import(PROTOCOL)
PROTOCOL_UNIT_OF_WORK = os.getenv('BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK', None)
PROTOCOL_UNIT_OF_WORK = NoneUnitOfWork if PROTOCOL_UNIT_OF_WORK is None else smart_import(PROTOCOL_UNIT_OF_WORK)
PROTOCOL_UNIT_OF_WORK_URL = os.getenv('BOLLYDOG_BUS_SERVICE_PROTOCOL_UNIT_OF_WORK_URL', 'memory://')
service_config = default_config.model_copy(
    update=dict(
        handlers=HANDLERS,
        protocol=ProtocolConfig(
            module=PROTOCOL,
            events=[],
            unit_of_work=UnitOfWorkConfig(
                module=PROTOCOL_UNIT_OF_WORK,
                url=PROTOCOL_UNIT_OF_WORK_URL,
            )
        )
    )
)
