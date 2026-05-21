"""Layer 4: E2E tests — full Hub lifecycle."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'example'))


async def test_execute_ping(hub):
    from example.commands import Ping
    result = await hub.execute(Ping())
    assert isinstance(result, dict)
    assert result['pong'] is True

async def test_execute_echo(hub):
    from example.commands import Echo
    result = await hub.execute(Echo(text='bollydog'))
    assert result == {'echo': 'bollydog'}

async def test_execute_echo_default(hub):
    from example.commands import Echo
    result = await hub.execute(Echo())
    assert result == {'echo': 'hello bollydog'}

async def test_hub_registry_populated(hub):
    from bollydog.models.base import BaseService
    assert len(BaseService.registry) > 0

async def test_hub_apps_populated(hub):
    from bollydog.models.service import AppService
    assert 'bollydog.Hub' in AppService._apps

async def test_globals_clean_after_hub():
    """After hub fixture teardown, globals should be clean (via clean_globals fixture)."""
    from bollydog.models.service import AppService
    from bollydog.models.base import BaseService
    assert len(AppService._apps) == 0
    assert len(BaseService.registry) == 0
