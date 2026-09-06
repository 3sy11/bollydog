"""Framework-level configuration: domain constant and entrypoint flags."""
import os

DOMAIN = 'bollydog'

ENTRYPOINT_HTTP_ENABLED = os.getenv('ENTRYPOINT_HTTP_ENABLED', '0') == '1'
ENTRYPOINT_WS_ENABLED = os.getenv('ENTRYPOINT_WS_ENABLED', '0') == '1'
ENTRYPOINT_UDS_ENABLED = os.getenv('ENTRYPOINT_UDS_ENABLED', '0') == '1'
