import os

SOCK_PATH = os.getenv('BOLLYDOG_UDS_SOCK_PATH', '/tmp/bollydog.sock')
SEND_DEFAULT_CONFIG = os.getenv('BOLLYDOG_SEND_DEFAULT_CONFIG') or None
