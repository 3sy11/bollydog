import logging
import os
import pathlib
import socket

logger = logging.getLogger(__name__)
WORKING_DIR = os.getenv('PWD', __file__)


def get_repository_version(path: str = WORKING_DIR):  # < tag and version
    path = pathlib.Path(path)
    while path != pathlib.Path('/'):
        logger.debug(f'get_repository_version: {path.name}')
        _git = path / '.git'
        if _git.exists() and _git.is_dir():
            break
        path = path.parent
    if path == pathlib.Path('/'):
        logger.warning(f'get_repository_version: not found')
        return '0000000'

    with open(path.as_posix() + '/.git/packed-refs', 'r') as f:
        v = f.readline().split('\t')[0]
        while v.startswith('#'):
            v = f.readline().split('\t')[0]
        logger.info(f'get_repository_version: {v[:7]}')
        return v[:7]


def get_hostname():
    return socket.gethostname()
