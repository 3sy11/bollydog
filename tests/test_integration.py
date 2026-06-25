"""Integration tests — CLI _resolve_command, Bootstrap, entrypoint logic via mock."""
import pytest
from unittest.mock import patch, MagicMock

from bollydog.globals import _registry_ctx_stack
from bollydog.models.base import BaseCommand
from bollydog.service.registry import RegistryService


# ─── helpers ─────────────────────────────────────────────────

def _make_registry_with(*cmd_classes, prefix='app.Svc'):
    """Create a RegistryService, populate bindings, push to context stack."""
    reg = RegistryService()
    for cls in cmd_classes:
        destination = f'{prefix}.{cls.alias}'
        reg.bindings[destination] = cls
    return reg


# ─── CLI: _resolve_command ────────────────────────────────────

def test_resolve_exact():
    from bollydog.entrypoint.cli import _resolve_command

    class Alpha(BaseCommand):
        async def __call__(self): return 1

    reg = _make_registry_with(Alpha)
    with _registry_ctx_stack.push(reg):
        dest, cls = _resolve_command('app.Svc.Alpha')
        assert cls is Alpha
        assert dest == 'app.Svc.Alpha'

def test_resolve_suffix():
    from bollydog.entrypoint.cli import _resolve_command

    class Alpha(BaseCommand):
        async def __call__(self): return 1

    reg = _make_registry_with(Alpha)
    with _registry_ctx_stack.push(reg):
        dest, cls = _resolve_command('Alpha')
        assert cls.alias == 'Alpha'

def test_resolve_not_found():
    from bollydog.entrypoint.cli import _resolve_command

    class Alpha(BaseCommand):
        async def __call__(self): return 1

    reg = _make_registry_with(Alpha)
    with _registry_ctx_stack.push(reg):
        with pytest.raises(KeyError, match="not found"):
            _resolve_command('NonExistent')

def test_resolve_ambiguous():
    from bollydog.entrypoint.cli import _resolve_command

    class Dup(BaseCommand):
        async def __call__(self): return 0

    reg = RegistryService()
    reg.bindings['a.S1.Dup'] = Dup
    reg.bindings['b.S2.Dup'] = Dup
    with _registry_ctx_stack.push(reg):
        with pytest.raises(KeyError, match="Ambiguous"):
            _resolve_command('Dup')


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


# ─── Exchange: match via registry.subscriptions ───────────────

def test_exchange_subscribe_unsubscribe():
    from bollydog.service.exchange import Exchange
    ex = Exchange()
    reg = RegistryService()
    with _registry_ctx_stack.push(reg):
        reg.subscribe('a.b.c', 'svc.Handler1')
        assert 'svc.Handler1' in ex.match('a.b.c')
        reg.unsubscribe('a.b.c', 'svc.Handler1')
        assert 'svc.Handler1' not in ex.match('a.b.c')

def test_exchange_pattern_subscribe():
    from bollydog.service.exchange import Exchange
    ex = Exchange()
    reg = RegistryService()
    with _registry_ctx_stack.push(reg):
        reg.subscribe('x.*.z', 'svc.Handler2')
        assert 'svc.Handler2' in ex.match('x.y.z')
        assert len(ex.match('x.q.z')) == 1
        assert len(ex.match('x.y.w')) == 0
