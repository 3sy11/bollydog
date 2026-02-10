import os

from bollydog.utils.base import get_repository_version, get_hostname

HOSTNAME = get_hostname()
REPOSITORY_VERSION = get_repository_version()
COMMAND_EXPIRE_TIME = int(os.getenv('BOLLYDOG_COMMAND_EXPIRE_TIME', 3600))
EVENT_EXPIRE_TIME = int(os.getenv('BOLLYDOG_EVENT_EXPIRE_TIME', 120))
QUEUE_MAX_SIZE = 1000
BOLLYDOG_HTTP_ENABLED = os.getenv('BOLLYDOG_HTTP_ENABLED', '1') == '1'
BOLLYDOG_WS_ENABLED = os.getenv('BOLLYDOG_WS_ENABLED', '1') == '1'
