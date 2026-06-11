"""Framework-level configuration: default services, env vars, constants."""
import os

DOMAIN = 'bollydog'

# Queue
QUEUE_MAX_SIZE = int(os.getenv('QUEUE_MAX_SIZE', 1000))
QUEUE_HISTORY_MAX_SIZE = int(os.getenv('QUEUE_HISTORY_MAX_SIZE', 1000))

# Entrypoint toggles
ENTRYPOINT_HTTP_ENABLED = os.getenv('ENTRYPOINT_HTTP_ENABLED', '0') == '1'
ENTRYPOINT_WS_ENABLED = os.getenv('ENTRYPOINT_WS_ENABLED', '0') == '1'
ENTRYPOINT_UDS_ENABLED = os.getenv('ENTRYPOINT_UDS_ENABLED', '0') == '1'

# All framework services (mode-agnostic, always fully built)
DEFAULT_SERVICES = {
    "bollydog.service.session.Session": {
        "protocol": {"module": "bollydog.adapters.memory.MemoryProtocol"}
    },
    "bollydog.service.exchange.Exchange": {},
    "bollydog.service.queue.Queue": {},
    "bollydog.service.app.HubService": {
        "router_mapping": {"TaskCount": ["GET", "/api/ping"]},
        "depends": ["bollydog.Exchange", "bollydog.Queue"],
    },
    "bollydog.service.executor.ExecuteService": {},
}

if ENTRYPOINT_HTTP_ENABLED:
    DEFAULT_SERVICES["bollydog.entrypoint.http.app.HttpService"] = {}
if ENTRYPOINT_WS_ENABLED:
    DEFAULT_SERVICES["bollydog.entrypoint.websocket.app.SocketService"] = {}
if ENTRYPOINT_UDS_ENABLED:
    DEFAULT_SERVICES["bollydog.entrypoint.uds.app.UdsService"] = {}
