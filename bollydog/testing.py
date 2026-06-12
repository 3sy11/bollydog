"""Test utilities for bollydog framework.

Layers:
  - command_context / run_command: unit-test a Command without Hub
  - run_hub: E2E context manager with HubService
  - run_execute: lightweight E2E with ExecuteService
"""
from contextlib import ExitStack, contextmanager, asynccontextmanager

from bollydog.bootstrap import Bootstrap
from bollydog.globals import (
    _app_ctx_stack, _protocol_ctx_stack, _message_ctx_stack,
    _services_ctx_stack, _session_ctx_stack, _hub_ctx_stack,
    _registry_ctx_stack,
)


@contextmanager
def command_context(app=None, protocol=None):
    """Push app/protocol context for unit-testing a Command outside Hub."""
    with ExitStack() as stack:
        if app: stack.enter_context(_app_ctx_stack.push(app))
        if protocol: stack.enter_context(_protocol_ctx_stack.push(protocol))
        yield


async def run_command(cmd, app=None, protocol=None):
    """Execute a single Command with context, return result."""
    with command_context(app, protocol):
        return await cmd()


@asynccontextmanager
async def run_hub(config: str = None):
    """E2E context manager: build services, start HubService, yield for testing."""
    bootstrap = Bootstrap(config=config)
    with ExitStack() as stack:
        stack.enter_context(_services_ctx_stack.push(bootstrap.services))
        if bootstrap.registry_service:
            stack.enter_context(_registry_ctx_stack.push(bootstrap.registry_service))
            bootstrap.registry_service.register()
        if bootstrap.session_service:
            stack.enter_context(_session_ctx_stack.push(bootstrap.session_service))
        stack.enter_context(_hub_ctx_stack.push(bootstrap.hub_service))
        async with bootstrap.hub_service:
            yield bootstrap.hub_service


@asynccontextmanager
async def run_execute(config: str = None):
    """Lightweight E2E: ExecuteService without Queue/Exchange."""
    bootstrap = Bootstrap(config=config)
    with ExitStack() as stack:
        stack.enter_context(_services_ctx_stack.push(bootstrap.services))
        if bootstrap.registry_service:
            stack.enter_context(_registry_ctx_stack.push(bootstrap.registry_service))
            bootstrap.registry_service.register()
        if bootstrap.session_service:
            stack.enter_context(_session_ctx_stack.push(bootstrap.session_service))
        async with bootstrap.executor_service:
            yield bootstrap.executor_service
