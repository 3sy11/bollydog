"""Integration tests — CLI _resolve_command, Bootstrap, entrypoint logic via mock."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from bollydog.models.base import BaseCommand, BaseService


# ─── CLI: _resolve_command ────────────────────────────────────

def _setup_registry():
    """Populate registry with test commands for resolve tests."""

    class Alpha(BaseCommand):
        async def __call__(self): return 1
    class Beta(BaseCommand):
        async def __call__(self): return 2

    a = Alpha._derive('app.Svc')
    b = Beta._derive('app.Svc')
    BaseService.registry.clear()
    BaseService.registry[a.destination] = a
    BaseService.registry[b.destination] = b
    return a, b


def test_resolve_exact():
    from bollydog.entrypoint.cli import _resolve_command
    a, b = _setup_registry()
    assert _resolve_command(a.destination) is a

def test_resolve_suffix():
    from bollydog.entrypoint.cli import _resolve_command
    _setup_registry()
    result = _resolve_command('Alpha')
    assert result.alias == 'Alpha'

def test_resolve_case_insensitive():
    from bollydog.entrypoint.cli import _resolve_command
    _setup_registry()
    result = _resolve_command('alpha')
    assert result.alias == 'Alpha'

def test_resolve_not_found():
    from bollydog.entrypoint.cli import _resolve_command
    _setup_registry()
    with pytest.raises(KeyError, match="not found"):
        _resolve_command('NonExistent')

def test_resolve_ambiguous():
    from bollydog.entrypoint.cli import _resolve_command

    class Dup(BaseCommand):
        async def __call__(self): return 0
    d1 = Dup._derive('a.S1')
    d2 = Dup._derive('b.S2')
    BaseService.registry.clear()
    BaseService.registry[d1.destination] = d1
    BaseService.registry[d2.destination] = d2
    with pytest.raises(KeyError, match="Ambiguous"):
        _resolve_command('Dup')


# ─── CLI: ls ──────────────────────────────────────────────────

def test_cli_ls_no_commands(capsys):
    from bollydog.entrypoint.cli import CLI
    BaseService.registry.clear()
    with patch('bollydog.entrypoint.cli.load_from_config'):
        CLI.ls(config=None)
    assert 'No commands registered' in capsys.readouterr().out

def test_cli_ls_with_commands(capsys):
    from bollydog.entrypoint.cli import CLI

    class Show(BaseCommand):
        name: str = ''
        async def __call__(self): return {}

    derived = Show._derive('app.Svc')
    BaseService.registry.clear()
    BaseService.registry[derived.destination] = derived
    with patch('bollydog.entrypoint.cli.load_from_config'):
        CLI.ls(config=None)
    out = capsys.readouterr().out
    assert 'Show' in out
    assert 'COMMAND' in out


# ─── Bootstrap ────────────────────────────────────────────────

def test_bootstrap_init():
    """Bootstrap can be instantiated with a real Service."""
    from bollydog.bootstrap import Bootstrap
    import mode
    svc = mode.Service()
    b = Bootstrap(svc, override_logging=False)
    assert b is not None


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


# ─── Exchange: match / subscribe / unsubscribe ────────────────

def test_exchange_subscribe_unsubscribe():
    from bollydog.service.exchange import Exchange
    ex = Exchange()

    class H1(BaseCommand):
        destination = 'a.b.c'
        async def __call__(self): return 1

    ex.subscribe('a.b.c', H1)
    assert H1 in ex.match('a.b.c')
    ex.unsubscribe('a.b.c', H1)
    assert H1 not in ex.match('a.b.c')

def test_exchange_pattern_subscribe():
    from bollydog.service.exchange import Exchange
    ex = Exchange()

    class H2(BaseCommand):
        destination = 'x.y.z'
        async def __call__(self): return 2

    ex.subscribe('x.*.z', H2)
    assert H2 in ex.match('x.y.z')
    assert len(ex.match('x.q.z')) == 1
    assert len(ex.match('x.y.w')) == 0

def test_exchange_list_topics():
    from bollydog.service.exchange import Exchange
    ex = Exchange()

    class H3(BaseCommand):
        destination = 'p.q.r'
        async def __call__(self): return 3

    ex.subscribe('p.q.r', H3)
    ex.subscribe('p.#', H3)
    topics = ex.list_topics()
    assert 'p.q.r' in topics['exact']
    assert 'p.#' in topics['patterns']
