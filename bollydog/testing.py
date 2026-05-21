"""Test utilities for bollydog framework.

Layers:
  - command_context / run_command: unit-test a Command without Hub
  - run_hub: E2E context manager — start Hub, yield, stop + cleanup

For E2E tests, use `async with run_hub() as h:` or `async with hub:` directly.
Hub.on_shutdown auto-cleans _apps and registry.
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
    """E2E context manager: load config, start Hub full lifecycle, yield for testing.

    async with run_hub('config.toml') as hub:
        result = await hub.execute(MyCommand(x=1))
    # Hub.__aexit__ -> stop + service_reset; on_shutdown clears _apps + registry
    """
    from bollydog.service import load_from_config
    from bollydog.models.service import AppService
    load_from_config(config)
    _hub = AppService._apps['bollydog.Hub']
    async with _hub:
        yield _hub
