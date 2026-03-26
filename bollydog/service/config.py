import os

from bollydog.utils.base import get_repository_version, get_hostname

DOMAIN = 'bollydog'
HOSTNAME = get_hostname()
REPOSITORY_VERSION = get_repository_version()
COMMAND_EXPIRE_TIME = int(os.getenv('BOLLYDOG_COMMAND_EXPIRE_TIME', 3600))
EVENT_EXPIRE_TIME = int(os.getenv('BOLLYDOG_EVENT_EXPIRE_TIME', 120))
QUEUE_MAX_SIZE = int(os.getenv('BOLLYDOG_QUEUE_MAX_SIZE', 1000))
HISTORY_MAX_SIZE = int(os.getenv('BOLLYDOG_HISTORY_MAX_SIZE', 1000))
DEFAULT_SIGN = int(os.getenv('BOLLYDOG_DEFAULT_SIGN', 1))
DELIVERY_COUNT = int(os.getenv('BOLLYDOG_DELIVERY_COUNT', 0))
DEFAULT_QOS = int(os.getenv('BOLLYDOG_DEFAULT_QOS', 1))
BOLLYDOG_HTTP_ENABLED = os.getenv('BOLLYDOG_HTTP_ENABLED', '0') == '1'
BOLLYDOG_WS_ENABLED = os.getenv('BOLLYDOG_WS_ENABLED', '0') == '1'
HUB_ROUTER_MAPPING = {'TaskCount': ['GET', '/api/ping']}
