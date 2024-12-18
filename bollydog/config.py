import os

from bollydog.utils.base import get_repository_version, get_hostname

HOSTNAME = get_hostname()
REPOSITORY_VERSION = get_repository_version()
MESSAGE_EXPIRE_TIME = int(os.getenv('BOLLYDOG_MESSAGE_EXPIRE_TIME', 3600))
IS_DEBUG = os.getenv('BOLLYDOG_IS_DEBUG', 'False') == 'True'
