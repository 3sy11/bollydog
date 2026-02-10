import logging
import asyncio
import pytest
from pydantic import Field

from bollydog.models.base import Command
from bollydog.service.app import HubService
from bollydog.exception import HandlerNoneError

logger = logging.getLogger(__name__)

class LogInfoCommand(Command):
    domain: str = Field(default='service')
    info: str = Field(default='info message')

class GenInfoCommand(Command):
    domain: str = Field(default='service')

class RaiseException(Command):
    domain: str = 'service'


@pytest.mark.asyncio
async def test_message_no_handler():
    """减法后，没有注册入口，所有 command 都应抛出 HandlerNoneError"""
    hub = HubService.create_from(domain='service', apps=[])
    command = LogInfoCommand(info='test')
    with pytest.raises(HandlerNoneError):
        hub.get_coro(command)


@pytest.mark.asyncio
async def test_execute_no_handler():
    hub = HubService.create_from(domain='service', apps=[])
    command = GenInfoCommand()
    with pytest.raises(HandlerNoneError):
        hub.get_coro(command)
