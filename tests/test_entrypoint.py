"""Entrypoint integration tests — HTTP/UDS/WS via mock + TestClient."""
import json
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from bollydog.models.base import BaseCommand, BaseService
from bollydog.models.service import AppService


# ─── Shared helpers ───────────────────────────────────────────

class _PingHttp(BaseCommand):
    async def __call__(self) -> dict:
        return {'pong': True}

class _EchoHttp(BaseCommand):
    text: str = 'hi'
    async def __call__(self) -> dict:
        return {'echo': self.text}


async def _fake_dispatch(msg):
    try:
        result = await msg()
        if not msg.state.done(): msg.state.set_result(result)
    except Exception as e:
        if not msg.state.done(): msg.state.set_exception(e)
    return msg


# ─── HTTP: HttpHandler via Starlette TestClient ──────────────

def test_http_get_route():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from bollydog.entrypoint.http.app import HttpHandler
    app = Starlette()
    app.add_route('/api/ping', HttpHandler(_PingHttp), methods=['GET'])
    with patch('bollydog.entrypoint.http.app.hub') as mock_hub:
        mock_hub.dispatch = AsyncMock(side_effect=_fake_dispatch)
        client = TestClient(app)
        resp = client.get('/api/ping')
    assert resp.status_code == 200
    assert resp.json()['pong'] is True

def test_http_post_json():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from bollydog.entrypoint.http.app import HttpHandler
    app = Starlette()
    app.add_route('/api/echo', HttpHandler(_EchoHttp), methods=['POST'])
    with patch('bollydog.entrypoint.http.app.hub') as mock_hub:
        mock_hub.dispatch = AsyncMock(side_effect=_fake_dispatch)
        client = TestClient(app)
        resp = client.post('/api/echo', json={'text': 'hello'})
    assert resp.status_code == 200
    assert resp.json()['echo'] == 'hello'

def test_http_post_empty_body():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from bollydog.entrypoint.http.app import HttpHandler
    app = Starlette()
    app.add_route('/api/echo', HttpHandler(_EchoHttp), methods=['POST'])
    with patch('bollydog.entrypoint.http.app.hub') as mock_hub:
        mock_hub.dispatch = AsyncMock(side_effect=_fake_dispatch)
        client = TestClient(app)
        resp = client.post('/api/echo', content=b'', headers={'content-type': 'application/json'})
    assert resp.status_code == 200
    assert resp.json()['echo'] == 'hi'

def test_http_error_returns_json():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from bollydog.entrypoint.http.app import HttpHandler

    class _Fail(BaseCommand):
        async def __call__(self): raise ValueError('boom')

    app = Starlette()
    app.add_route('/api/fail', HttpHandler(_Fail), methods=['GET'])
    with patch('bollydog.entrypoint.http.app.hub') as mock_hub:
        mock_hub.dispatch = AsyncMock(side_effect=_fake_dispatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get('/api/fail')
    assert resp.status_code == 200
    assert 'error' in resp.json()

def test_http_html_response():
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from bollydog.entrypoint.http.app import HttpHandler

    class _Html(BaseCommand):
        async def __call__(self) -> str: return '<h1>Hello</h1>'

    app = Starlette()
    app.add_route('/html', HttpHandler(_Html), methods=['GET'])
    with patch('bollydog.entrypoint.http.app.hub') as mock_hub:
        mock_hub.dispatch = AsyncMock(side_effect=_fake_dispatch)
        client = TestClient(app)
        resp = client.get('/html')
    assert resp.status_code == 200
    assert '<h1>Hello</h1>' in resp.text


# ─── HTTP: HubContextMiddleware ──────────────────────────────

async def test_hub_context_middleware():
    from bollydog.entrypoint.http.app import HubContextMiddleware
    calls = []
    async def inner(scope, receive, send): calls.append(scope)
    mock_hub = MagicMock()
    mw = HubContextMiddleware(inner, mock_hub)
    with patch('bollydog.entrypoint.http.app._hub_ctx_stack'):
        await mw({'type': 'http'}, None, None)
    assert len(calls) == 1

def test_hub_context_middleware_init():
    from bollydog.entrypoint.http.app import HubContextMiddleware
    mw = HubContextMiddleware(MagicMock(), MagicMock())
    assert mw.hub_instance is not None


# ─── HTTP: HttpService helpers ────────────────────────────────

def test_http_service_build_middlewares():
    from bollydog.entrypoint.http.app import HttpService
    with patch.dict('os.environ', {}, clear=False):
        mws = HttpService._build_middlewares()
        assert isinstance(mws, list)

def test_http_service_collect_router_mappings():
    from bollydog.entrypoint.http.app import HttpService
    mock_svc = MagicMock()
    mock_svc.router_mapping = {'Ping': ['GET', '/api/ping']}
    mock_svc._children = []
    result = HttpService._collect_router_mappings(mock_svc)
    assert result == {'Ping': ['GET', '/api/ping']}

def test_http_handler_init():
    from bollydog.entrypoint.http.app import HttpHandler
    h = HttpHandler(_PingHttp)
    assert h.message is _PingHttp

def test_sse_handler_init():
    from bollydog.entrypoint.http.app import SseHandler

    class _Stream(BaseCommand):
        async def __call__(self): yield 1

    h = SseHandler(_Stream)
    assert h.message is _Stream


# ─── HTTP: ASGIMiddleware ─────────────────────────────────────

async def test_asgi_middleware_passthrough():
    from bollydog.entrypoint.http.middleware import ASGIMiddleware
    calls = []
    async def app(scope, receive, send): calls.append(1)
    mw = ASGIMiddleware(app)
    await mw({'type': 'http'}, None, None)
    assert len(calls) == 1


# ─── UDS: frame protocol ─────────────────────────────────────

def test_uds_write_frame():
    import io
    from bollydog.entrypoint.uds.app import _write_frame

    class FakeWriter:
        def __init__(self): self.buf = io.BytesIO()
        def write(self, data): self.buf.write(data)

    w = FakeWriter()
    _write_frame(w, '{"hello":"world"}')
    raw = w.buf.getvalue()
    length = int.from_bytes(raw[:4], 'big')
    payload = raw[4:4+length].decode()
    assert json.loads(payload) == {'hello': 'world'}

async def test_uds_read_frame():
    from bollydog.entrypoint.uds.app import _read_frame
    payload = b'{"ok":true}'
    frame = len(payload).to_bytes(4, 'big') + payload
    reader = asyncio.StreamReader()
    reader.feed_data(frame)
    result = await _read_frame(reader)
    assert json.loads(result) == {'ok': True}

def test_uds_service_init():
    from bollydog.entrypoint.uds.app import UdsService
    svc = UdsService(sock_path='/tmp/test.sock')
    assert svc._sock_path == '/tmp/test.sock'
    assert svc._server is None


# ─── WebSocket: SocketService ─────────────────────────────────

def test_socket_service_init():
    from bollydog.entrypoint.websocket.app import SocketService
    svc = SocketService()
    assert svc.subscribers == set()
    assert svc.listening == {}

async def test_socket_service_subscribe():
    from bollydog.entrypoint.websocket.app import SocketService
    svc = SocketService()
    ws = AsyncMock()
    await svc.subscribe(ws)
    assert ws in svc.subscribers
    ws.accept.assert_awaited_once()

async def test_socket_service_unsubscribe():
    from bollydog.entrypoint.websocket.app import SocketService
    svc = SocketService()
    ws = AsyncMock()
    await svc.subscribe(ws)
    svc.listening['trace1'] = {ws}
    await svc.unsubscribe(ws)
    assert ws not in svc.subscribers
    assert 'trace1' not in svc.listening


# ─── Bootstrap ────────────────────────────────────────────────

def test_bootstrap_init():
    from bollydog.bootstrap import Bootstrap
    import mode
    svc = mode.Service()
    b = Bootstrap(svc, override_logging=False)
    assert b is not None

def test_bootstrap_on_init_dependencies():
    from bollydog.bootstrap import Bootstrap
    import mode
    svc = mode.Service()
    b = Bootstrap(svc, override_logging=False)
    deps = b.on_init_dependencies()
    assert svc in deps
