"""Global fixtures for bollydog tests.

- clean_globals (autouse): reset registry / LocalStack after each test
- memory_protocol: standalone MemoryProtocol with lifecycle
- hub: full E2E Hub with config loaded
"""
import pytest
from bollydog.models.base import BaseService
from bollydog.globals import (
    _hub_ctx_stack, _protocol_ctx_stack, _message_ctx_stack,
    _session_ctx_stack, _app_ctx_stack, _apps_ctx_stack,
)


@pytest.fixture(autouse=True)
async def clean_globals():
    yield
    BaseService.registry.clear()
    for stack in (_hub_ctx_stack, _protocol_ctx_stack, _message_ctx_stack, _session_ctx_stack, _app_ctx_stack, _apps_ctx_stack):
        while stack.top is not None:
            stack.pop()


@pytest.fixture
async def memory_protocol():
    from bollydog.adapters.memory import MemoryProtocol
    proto = MemoryProtocol()
    async with proto:
        yield proto


@pytest.fixture
async def hub():
    from bollydog.testing import run_hub
    async with run_hub() as h:
        yield h
