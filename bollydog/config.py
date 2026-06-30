"""Framework-level configuration: default services, env vars, constants."""
import os

from bollydog.entrypoint.http.config import ENTRYPOINT_HTTP_SERVICE_CONFIG
from bollydog.entrypoint.uds.config import ENTRYPOINT_UDS_SERVICE_CONFIG
from bollydog.entrypoint.websocket.config import ENTRYPOINT_WS_SERVICE_CONFIG

DOMAIN = 'bollydog'

# Queue
QUEUE_MAX_SIZE = int(os.getenv('QUEUE_MAX_SIZE', 1000))
QUEUE_HISTORY_MAX_SIZE = int(os.getenv('QUEUE_HISTORY_MAX_SIZE', 1000))

SERVICE_CONFIG = {
    "bollydog.service.registry.RegistryService": {},
    "bollydog.service.session.Session": {
        "protocol": {"module": "bollydog.adapters.memory.MemoryProtocol"}
    },
    "bollydog.service.exchange.Exchange": {},
    "bollydog.service.queue.Queue": {},
    "bollydog.service.app.HubService": {
        "routers": {"TaskCount": ["GET", "/api/ping"]},
        "depends": ["bollydog.Exchange", "bollydog.Queue"],
    },
    "bollydog.service.executor.ExecuteService": {},
    **ENTRYPOINT_HTTP_SERVICE_CONFIG,
    **ENTRYPOINT_WS_SERVICE_CONFIG,
    **ENTRYPOINT_UDS_SERVICE_CONFIG,
}
