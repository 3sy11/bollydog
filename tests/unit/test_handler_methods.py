import pytest
from pydantic import Field
from unittest.mock import Mock

from bollydog.models.base import Command, BaseMessage
from bollydog.service.handler import AppHandler


class TestCommand(Command):
    domain: str = Field(default='test')
    data: str = Field(default="test_data")


class TestCommand2(Command):
    domain: str = Field(default='test')
    value: int = Field(default=42)


class TestAppService:
    def __init__(self, domain="test", name="test_app"):
        self.domain = domain
        self.name = name
        self.protocol = Mock()
    def __str__(self):
        return f"{self.domain}:{self.name}"


class TestHandlerMethods:

    def setup_method(self):
        AppHandler.messages.clear()
        AppHandler.commands.clear()

    @pytest.mark.asyncio
    async def test_get_message_handlers_empty(self):
        handlers = AppHandler.get_message_handlers(TestCommand)
        assert len(handlers) == 0

    @pytest.mark.asyncio
    async def test_get_message_handlers_base_message(self):
        handlers = AppHandler.get_message_handlers(BaseMessage)
        assert len(handlers) == 0

    def test_get_message_handlers_class_method(self):
        assert hasattr(AppHandler, 'get_message_handlers')
        assert callable(AppHandler.get_message_handlers)
        handlers = AppHandler.get_message_handlers(TestCommand)
        assert isinstance(handlers, list)
