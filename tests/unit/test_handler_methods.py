

import pytest
import inspect
from pydantic import Field
from unittest.mock import Mock, patch, MagicMock

from bollydog.models.base import Command, Event, BaseMessage, get_model_name
from bollydog.service.handler import AppHandler


class TestCommand(Command):
    domain: str = Field(default='test')
    data: str = Field(default="test_data")


class TestEvent(Event):
    domain: str = Field(default='test')
    data: str = Field(default="test_event_data")


class TestCommand2(Command):
    domain: str = Field(default='test')
    value: int = Field(default=42)


class TestEvent2(Event):
    domain: str = Field(default='test')
    value: int = Field(default=100)

async def command_handler(message: TestCommand):
    return f"processed: {message.data}"


async def event_handler(message: TestEvent):
    return f"event processed: {message.data}"


async def command2_handler(message: TestCommand2):
    return f"command2 processed: {message.value}"


async def event2_handler(message: TestEvent2):
    return f"event2 processed: {message.value}"


class TestModuleCommand(Command):
    domain: str = Field(default='test')
    
    async def __call__(self):
        return "module command"


class TestModuleEvent(Event):
    domain: str = Field(default='test')
    
    async def __call__(self):
        return "module event"


class TestModuleCommandAsyncGen(Command):
    domain: str = Field(default='test')
    
    async def __call__(self):
        yield TestEvent(data="yielded from module command")


class TestModuleEventAsyncGen(Event):
    domain: str = Field(default='test')
    
    async def __call__(self):
        yield TestCommand(data="yielded from module event")


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
        AppHandler.events.clear()

    @pytest.mark.asyncio
    async def test_get_message_handlers_command(self):
        app = TestAppService(domain="test", name="test_app")
        AppHandler.register(TestCommand, command_handler, app)
        handlers = AppHandler.get_message_handlers(TestCommand)

        assert len(handlers) == 1
        assert handlers[0].fun == command_handler
        assert handlers[0].app == app
        assert handlers[0].isasyncgenfunction is False

    @pytest.mark.asyncio
    async def test_get_message_handlers_event(self):
        app = TestAppService(domain="test", name="test_app")
        AppHandler.register(TestEvent, event_handler, app)
        handlers = AppHandler.get_message_handlers(TestEvent)
        assert len(handlers) == 1
        assert handlers[0].fun == event_handler
        assert handlers[0].app == app
        assert handlers[0].isasyncgenfunction is False

    @pytest.mark.asyncio
    async def test_get_message_handlers_event_multiple(self):
        app1 = TestAppService(domain="test", name="test_app1")
        app2 = TestAppService(domain="test", name="test_app2")
        app3 = TestAppService(domain="test", name="test_app3")
        
        AppHandler.register(TestEvent, event_handler, app1)
        AppHandler.register(TestEvent, event_handler, app2)
        AppHandler.register(TestEvent, event_handler, app3)
        
        handlers = AppHandler.get_message_handlers(TestEvent)
        
        assert len(handlers) == 3
        assert handlers[0].fun == event_handler
        assert handlers[0].app == app1
        assert handlers[1].fun == event_handler
        assert handlers[1].app == app2
        assert handlers[2].fun == event_handler
        assert handlers[2].app == app3

    @pytest.mark.asyncio
    async def test_get_message_handlers_nonexistent(self):
        handlers = AppHandler.get_message_handlers(TestCommand)
        assert len(handlers) == 0

    @pytest.mark.asyncio
    async def test_get_message_handlers_base_message(self):
        handlers = AppHandler.get_message_handlers(BaseMessage)
        assert len(handlers) == 0

    @pytest.mark.asyncio
    async def test_get_message_handlers_mixed_types(self):
        app1 = TestAppService(domain="test", name="test_app1")
        app2 = TestAppService(domain="test", name="test_app2")
        
        AppHandler.register(TestCommand, command_handler, app1)
        AppHandler.register(TestEvent, event_handler, app2)
        
        command_handlers = AppHandler.get_message_handlers(TestCommand)
        event_handlers = AppHandler.get_message_handlers(TestEvent)
        
        assert len(command_handlers) == 1
        assert command_handlers[0].fun == command_handler
        assert command_handlers[0].app == app1
        
        assert len(event_handlers) == 1
        assert event_handlers[0].fun == event_handler
        assert event_handlers[0].app == app2

    @pytest.mark.asyncio
    async def test_walk_module_with_classes(self):
        app = TestAppService(domain="test", name="test_app")
        
        test_module = type('TestModule', (), {
            'TestModuleCommand': TestModuleCommand,
            'TestModuleEvent': TestModuleEvent,
            'TestModuleCommandAsyncGen': TestModuleCommandAsyncGen,
            'TestModuleEventAsyncGen': TestModuleEventAsyncGen,
            'simple_function': lambda: None,  # 普通函数，应该被忽略
            'command_handler': command_handler  # 函数，应该被处理
        })
        
        AppHandler.walk_module(test_module, app)
        
        assert TestModuleCommand in AppHandler.commands
        assert TestModuleEvent in AppHandler.events
        assert TestModuleCommandAsyncGen in AppHandler.commands
        assert TestModuleEventAsyncGen in AppHandler.events
        
        assert TestCommand in AppHandler.commands

    @pytest.mark.asyncio
    async def test_walk_module_with_functions(self):
        app = TestAppService(domain="test", name="test_app")
        
        test_module = type('TestModule', (), {
            'command_handler': command_handler,
            'event_handler': event_handler,
            'command2_handler': command2_handler,
            'event2_handler': event2_handler
        })
        
        AppHandler.walk_module(test_module, app)
        
        assert TestCommand in AppHandler.commands
        assert TestEvent in AppHandler.events
        assert TestCommand2 in AppHandler.commands
        assert TestEvent2 in AppHandler.events

    @pytest.mark.asyncio
    async def test_walk_module_string_import(self):
        app = TestAppService(domain="test", name="test_app")
        
        AppHandler.walk_module("nonexistent.module", app)
        
        assert len(AppHandler.commands) == 0
        assert len(AppHandler.events) == 0

    @pytest.mark.asyncio
    async def test_walk_module_with_invalid_classes(self):
        app = TestAppService(domain="test", name="test_app")
        
        class InvalidClass:
            pass
        
        class CommandWithoutCall(Command):
            domain: str = Field(default='test')

        class EventWithoutAsyncCall(Event):
            domain: str = Field(default='test')
            
            def __call__(self):
                return "sync call"
        
        test_module = type('TestModule', (), {
            'InvalidClass': InvalidClass,
            'CommandWithoutCall': CommandWithoutCall,
            'EventWithoutAsyncCall': EventWithoutAsyncCall,
            'TestModuleCommand': TestModuleCommand
        })
        
        AppHandler.walk_module(test_module, app)
        
        assert TestModuleCommand in AppHandler.commands
        assert CommandWithoutCall not in AppHandler.commands
        assert EventWithoutAsyncCall not in AppHandler.events
        assert InvalidClass not in AppHandler.commands
        assert InvalidClass not in AppHandler.events

    @pytest.mark.asyncio
    async def test_walk_module_exception_handling(self):
        app = TestAppService(domain="test", name="test_app")
        class ExceptionClass:
            def __init__(self):
                raise ValueError("Test exception")
        
        test_module = type('TestModule', (), {
            'ExceptionClass': ExceptionClass,
            'TestModuleCommand': TestModuleCommand
        })
        
        AppHandler.walk_module(test_module, app)
        assert TestModuleCommand in AppHandler.commands

    @pytest.mark.asyncio
    async def test_walk_module_empty_module(self):
        app = TestAppService(domain="test", name="test_app")
        empty_module = type('EmptyModule', (), {})
        AppHandler.walk_module(empty_module, app)
        assert len(AppHandler.commands) == 0
        assert len(AppHandler.events) == 0

    @pytest.mark.asyncio
    async def test_walk_module_with_async_generator_classes(self):
        app = TestAppService(domain="test", name="test_app")
        
        test_module = type('TestModule', (), {
            'TestModuleCommandAsyncGen': TestModuleCommandAsyncGen,
            'TestModuleEventAsyncGen': TestModuleEventAsyncGen
        })
        
        AppHandler.walk_module(test_module, app)
        
        assert TestModuleCommandAsyncGen in AppHandler.commands
        assert TestModuleEventAsyncGen in AppHandler.events
        
        command_handler = AppHandler.commands[TestModuleCommandAsyncGen]
        event_handler = AppHandler.events[TestModuleEventAsyncGen][0]
        
        assert command_handler.isasyncgenfunction is True
        assert event_handler.isasyncgenfunction is True

    @pytest.mark.asyncio
    async def test_get_message_handlers_after_walk_module(self):
        app = TestAppService(domain="test", name="test_app")
        
        test_module = type('TestModule', (), {
            'TestModuleCommand': TestModuleCommand,
            'TestModuleEvent': TestModuleEvent,
            'command_handler': command_handler
        })
        
        AppHandler.walk_module(test_module, app)
        
        command_handlers = AppHandler.get_message_handlers(TestModuleCommand)
        event_handlers = AppHandler.get_message_handlers(TestModuleEvent)
        test_command_handlers = AppHandler.get_message_handlers(TestCommand)
        
        assert len(command_handlers) == 1
        assert command_handlers[0].fun == TestModuleCommand.__call__
        assert command_handlers[0].app == app
        
        assert len(event_handlers) == 1
        assert event_handlers[0].fun == TestModuleEvent.__call__
        assert event_handlers[0].app == app
        
        assert len(test_command_handlers) == 1
        assert test_command_handlers[0].fun == command_handler
        assert test_command_handlers[0].app == app

    def test_get_message_handlers_class_method(self):

        assert hasattr(AppHandler, 'get_message_handlers')
        assert callable(AppHandler.get_message_handlers)
        
        handlers = AppHandler.get_message_handlers(TestCommand)
        assert isinstance(handlers, list)

    def test_walk_module_class_method(self):

        assert hasattr(AppHandler, 'walk_module')
        assert callable(AppHandler.walk_module)
        
        app = TestAppService(domain="test", name="test_app")
        empty_module = type('EmptyModule', (), {})
        AppHandler.walk_module(empty_module, app)

    @pytest.mark.asyncio
    async def test_walk_module_with_union_annotations(self):
        app = TestAppService(domain="test", name="test_app")
        
        async def union_handler(message: TestCommand | TestEvent):
            return f"union processed: {type(message).__name__}"
        
        test_module = type('TestModule', (), {
            'union_handler': union_handler
        })
        
        AppHandler.walk_module(test_module, app)
        
        command_handlers = AppHandler.get_message_handlers(TestCommand)
        event_handlers = AppHandler.get_message_handlers(TestEvent)
        
        assert len(command_handlers) == 0
        assert len(event_handlers) == 0 