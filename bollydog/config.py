import os

from bollydog.utils.base import get_repository_version, get_hostname

HOSTNAME = get_hostname()
REPOSITORY_VERSION = get_repository_version()
MESSAGE_EXPIRE_TIME = os.getenv('BOLLYDOG_MESSAGE_EXPIRE_TIME', 60)  # 60 seconds
IS_DEBUG = os.getenv('BOLLYDOG_IS_DEBUG', 'False') == 'True'
