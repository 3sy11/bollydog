import os

DOMAIN = 'bollydog'
QUEUE_MAX_SIZE = int(os.getenv('QUEUE_MAX_SIZE', 1000))
QUEUE_HISTORY_MAX_SIZE = int(os.getenv('QUEUE_HISTORY_MAX_SIZE', 1000))
