import asyncio
import inspect
import json
import logging
from typing import Type

import mode
import uvicorn
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, StreamingResponse

from bollydog.globals import hub, services, registry, _hub_ctx_stack
from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService

from .middleware import base_auth_backend


class HubContextMiddleware:
    """Uvicorn creates a fresh contextvars.Context per request, losing _hub_ctx_stack.
    This middleware re-injects hub into each ASGI scope."""
    def __init__(self, app, hub_instance):
        self.app, self.hub_instance = app, hub_instance

    async def __call__(self, scope, receive, send):
        _hub_ctx_stack.push_without_automatic_cleanup(self.hub_instance)
        try:
            await self.app(scope, receive, send)
        finally:
            _hub_ctx_stack.pop()

class HttpHandler:

    def __init__(self, message: Type[BaseCommand]):
        self.message = message

    async def __call__(self, scope, receive, send):
        request = Request(scope, receive=receive, send=send)
        username = getattr(scope.get('user'), 'display_name', None)
        try:
            if request.method == 'GET':
                message: BaseCommand = self.message(**request.query_params, **request.path_params, created_by=username)
            elif request.method == 'POST':
                content_type = request.headers.get('content-type', '')
                if 'multipart/form-data' in content_type:
                    _data = dict()
                    data = await request.form()
                    for k, v in data.items():
                        if isinstance(v, UploadFile):
                            file = await v.read()
                            v = {'file': file, 'filename': v.filename, 'content_type': v.content_type, 'size': v.size}
                        _data[k] = v
                    data = _data
                else:
                    body = await request.body()
                    data = await request.json() if body.strip() else {}
                data = {**dict(request.query_params), **data}
                message: BaseCommand = self.message(**data, **request.path_params, created_by=username)
            else:
                raise NotImplementedError
            message = await hub.dispatch(message)
            result = await message.state
        except Exception as e:
            result = {'error': str(e)}
            logging.error(e)
        if isinstance(result, str):
            response = HTMLResponse(result)
        else:
            response = JSONResponse(result)
        await response(scope, receive, send)


class SseHandler:

    def __init__(self, message: Type[BaseCommand]):
        self.message = message

    async def __call__(self, scope, receive, send):
        request = Request(scope, receive=receive, send=send)
        username = getattr(scope.get('user'), 'display_name', None)
        if request.method == 'GET':
            message = self.message(**request.query_params, **request.path_params, created_by=username)
        else:
            data = await request.json()
            message = self.message(**data, **request.path_params, created_by=username)

        async def event_stream():
            task = asyncio.create_task(hub.execute(message))
            try:
                async for value in message.state:
                    yield f"data: {json.dumps(value, ensure_ascii=False)}\n\n"
            finally:
                if not task.done(): task.cancel()

        response = StreamingResponse(event_stream(), media_type='text/event-stream',
                                     headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})
        await response(scope, receive, send)


class HttpService(AppService):
    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = False
    log_level: str = 'info'
    private_key_path: str = None
    public_key_path: str = None
    loop: str = 'uvloop'
    http: str = 'httptools'
    limit_concurrency: int = None
    limit_max_requests: int = 2000
    timeout_keep_alive: int = 5
    backlog: int = 128
    middleware_session: bool = True
    middleware_auth: bool = True
    middleware_cors: bool = True
    middleware_sessions_secret_key: str = ''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = self
        self.http_app = Starlette()
        self.uvicorn = None

    def _build_middlewares(self):
        mws = []
        if self.middleware_session:
            mws.append(Middleware(SessionMiddleware, secret_key=self.middleware_sessions_secret_key))
        if self.middleware_auth:
            mws.append(Middleware(AuthenticationMiddleware, backend=base_auth_backend))
        if self.middleware_cors:
            mws.append(Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], max_age=1728000))
        return mws

    @staticmethod
    def _collect_routers(service, visited=None):
        if visited is None: visited = set()
        if id(service) in visited: return {}
        visited.add(id(service))
        rm = dict(service.routers)
        for child in getattr(service, '_children', []):
            rm.update(HttpService._collect_routers(child, visited))
        return rm

    async def on_start(self) -> None:
        _merged = {}
        for service in services.values():
            _merged.update(self._collect_routers(service))
        for destination, cmd_cls in registry.all_commands().items():
            cmd_alias = cmd_cls.alias
            _route = _merged.get(cmd_cls.__name__, _merged.get(cmd_alias, _merged.get(destination)))
            if _route is None: continue
            _methods = _route[0] if len(_route) > 0 else 'GET'
            _methods = [_methods] if isinstance(_methods, str) else _methods
            _path = _route[1] if len(_route) > 1 else None
            if not _path:
                _domain = destination.split('.')[0]
                _path = f'/api/{_domain}/{cmd_alias}'
            if 'SSE' in _methods:
                _methods = ['GET']
                if inspect.isasyncgenfunction(cmd_cls.__call__):
                    _handler = SseHandler(cmd_cls)
                else:
                    logging.warning(f'{cmd_alias} mapped as SSE but is not async generator, falling back to HTTP')
                    _handler = HttpHandler(cmd_cls)
            else:
                _handler = HttpHandler(cmd_cls)
            self.http_app.router.add_route(_path, _handler, methods=_methods, name=cmd_alias, include_in_schema=True)
        self.http_app.user_middleware = self._build_middlewares()
        self.http_app.debug = self.debug
        self._asgi_app = HubContextMiddleware(self.http_app, hub._get_current_object())
        self.init_server()
        await super(HttpService, self).on_start()

    async def on_started(self) -> None:
        scheme = 'https' if self.private_key_path else 'http'
        base = f'{scheme}://{self.host}:{self.port}'
        routes = [r for r in self.http_app.routes if hasattr(r, 'path')]
        lines = '\n  '.join(f'{",".join(r.methods)} {base}{r.path} -> {r.name}' for r in routes)
        self.logger.info(f'http({len(routes)} routes) {base}\n  {lines}')
        await super(HttpService, self).on_started()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(
            host=self.host,
            app=self._asgi_app,
            port=int(self.port),
            log_level=self.log_level,
            ssl_keyfile=self.private_key_path,
            ssl_certfile=self.public_key_path,
            loop=self.loop,
            http=self.http,
            limit_concurrency=self.limit_concurrency,
            limit_max_requests=self.limit_max_requests,
            timeout_keep_alive=self.timeout_keep_alive,
            backlog=self.backlog
        )
        self.uvicorn = uvicorn.Server(config)

    async def on_stop(self) -> None:
        try:
            if self.uvicorn:
                self.uvicorn.should_exit = True
                await asyncio.sleep(0.3)
                await self.uvicorn.shutdown()
        except Exception as e:
            self.logger.error(e)
        await super(HttpService, self).on_stop()
