"""Integration tests — RegistryService resolve, CLI ls, Bootstrap, entrypoint logic via mock."""
import pytest
from unittest.mock import patch, MagicMock

from bollydog.globals import _registry_ctx_stack
from bollydog.models.base import BaseCommand
from bollydog.service.registry import RegistryService


# ─── helpers ─────────────────────────────────────────────────

def _make_registry_with(*cmd_classes, prefix='app.Svc'):
    """Create a RegistryService, populate _commands, push to context stack."""
    reg = RegistryService()
    for cls in cmd_classes:
        destination = f'{prefix}.{cls.alias}'
        reg._commands[destination] = cls
    return reg


# ─── RegistryService: resolve ─────────────────────────────────

def test_resolve_exact():
    class Alpha(BaseCommand):
        async def __call__(self): return 1

    reg = _make_registry_with(Alpha)
    with _registry_ctx_stack.push(reg):
        cls = reg.resolve('app.Svc.Alpha')
        assert cls is Alpha

def test_resolve_not_found():
    class Alpha(BaseCommand):
        async def __call__(self): return 1

    reg = _make_registry_with(Alpha)
    with _registry_ctx_stack.push(reg):
        with pytest.raises(KeyError, match="not found"):
            reg.resolve('NonExistent')


# ─── CLI: ls ──────────────────────────────────────────────────

def test_cli_ls_no_commands(capsys):
    from bollydog.entrypoint.cli import CLI
    reg = RegistryService()
    with _registry_ctx_stack.push(reg):
        with patch('bollydog.entrypoint.cli.Bootstrap'):
            CLI.ls(config=None)
    assert 'No commands registered' in capsys.readouterr().out

def test_cli_ls_with_commands(capsys):
    from bollydog.entrypoint.cli import CLI

    class Show(BaseCommand):
        name: str = ''
        async def __call__(self): return {}

    reg = _make_registry_with(Show)
    with _registry_ctx_stack.push(reg):
        with patch('bollydog.entrypoint.cli.Bootstrap'):
            CLI.ls(config=None)
    out = capsys.readouterr().out
    assert 'Show' in out
    assert 'COMMAND' in out


# ─── Bootstrap ────────────────────────────────────────────────

def test_bootstrap_init():
    """Bootstrap can be instantiated without config."""
    from bollydog.bootstrap import Bootstrap
    b = Bootstrap(override_logging=False)
    assert b is not None
    assert isinstance(b.services, dict)


# ─── HttpService mock ────────────────────────────────────────

def test_http_handler_init():
    """HttpHandler wraps a Command class."""
    from bollydog.entrypoint.http.app import HttpHandler

    class Req(BaseCommand):
        async def __call__(self): return {}

    h = HttpHandler(Req)
    assert h.message is Req

def test_sse_handler_init():
    """SseHandler wraps an async gen Command class."""
    from bollydog.entrypoint.http.app import SseHandler

    class Stream(BaseCommand):
        async def __call__(self): yield {}

    h = SseHandler(Stream)
    assert h.message is Stream

def test_hub_context_middleware_init():
    from bollydog.entrypoint.http.app import HubContextMiddleware
    mock_app = MagicMock()
    mock_hub = MagicMock()
    mw = HubContextMiddleware(mock_app, mock_hub)
    assert mw.hub_instance is mock_hub


# ─── Exchange: topic -> Event class index ─────────────────────

def test_exchange_add_remove_event():
    from bollydog.models.base import BaseEvent
    from bollydog.service.exchange import Exchange

    class _Handler1(BaseEvent):
        destination = 'svc.Handler1'

    ex = Exchange()
    ex.add_event('a.b.c', _Handler1)
    assert _Handler1 in ex.match('a.b.c')
    assert ex.resolve('svc.Handler1') is _Handler1
    ex.remove_event('a.b.c', _Handler1)
    assert _Handler1 not in ex.match('a.b.c')

def test_exchange_pattern_match():
    from bollydog.models.base import BaseEvent
    from bollydog.service.exchange import Exchange

    class _Handler2(BaseEvent):
        destination = 'svc.Handler2'

    ex = Exchange()
    ex.add_event('x.*.z', _Handler2)
    assert _Handler2 in ex.match('x.y.z')
    assert len(ex.match('x.q.z')) == 1
    assert len(ex.match('x.y.w')) == 0

def test_exchange_instantiate():
    from bollydog.models.base import BaseEvent
    from bollydog.service.exchange import Exchange

    class _Handler3(BaseEvent):
        destination = 'svc.Handler3'

    ex = Exchange()
    ex.add_event('p.q', _Handler3)
    events = ex.instantiate('p.q')
    assert len(events) == 1 and isinstance(events[0], _Handler3)
