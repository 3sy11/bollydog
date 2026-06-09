"""Test utilities for bollydog framework.

Layers:
  - command_context / run_command: unit-test a Command without Hub
  - run_hub: E2E context manager with HubService — start full pipeline, yield, stop + cleanup
  - run_execute: lightweight E2E with ExecuteService — no Queue/Exchange
"""
from contextlib import contextmanager, asynccontextmanager
from bollydog.globals import _app_ctx_stack, _protocol_ctx_stack, _message_ctx_stack


@contextmanager
def command_context(app=None, protocol=None):
    """Push app/protocol context for unit-testing a Command outside Hub."""
    from contextlib import ExitStack
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
    """E2E context manager: load config, start HubService full lifecycle, yield for testing.

    async with run_hub('config.toml') as hub:
        result = await hub.execute(MyCommand(x=1))
    # HubService.__aexit__ -> stop + service_reset; Bootstrap.on_shutdown clears _apps + registry
    """
    from bollydog.service import parse_config, build_services
    from bollydog.models.service import AppService
    parsed = parse_config(config)
    build_services(parsed, mode='service')
    _hub = AppService._apps['bollydog.HubService']
    async with _hub:
        yield _hub


@asynccontextmanager
async def run_execute(config: str = None):
    """Lightweight E2E: ExecuteService without Queue/Exchange.

    async with run_execute('config.toml') as executor:
        result = await executor.execute(MyCommand(x=1))
    """
    from bollydog.service import parse_config, build_services
    from bollydog.models.service import AppService
    parsed = parse_config(config)
    build_services(parsed, mode='execute')
    _executor = AppService._apps['bollydog.ExecuteService']
    async with _executor:
        yield _executor
