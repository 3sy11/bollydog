import asyncio
import json
from typing import Type
import logging
import mode
import uvicorn
from bollydog.models.service import AppService
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, StreamingResponse
from starlette.datastructures import UploadFile

from bollydog.globals import hub, _hub_ctx_stack
from bollydog.models.base import BaseCommand


class HubContextMiddleware:
    """uvicorn 为每个请求创建 contextvars.Context() 空上下文，
    导致 _hub_ctx_stack 丢失。此中间件为每个 ASGI scope 重新注入 hub。"""
    def __init__(self, app, hub_instance):
        self.app, self.hub_instance = app, hub_instance

    async def __call__(self, scope, receive, send):
        _hub_ctx_stack.push_without_automatic_cleanup(self.hub_instance)
        try:
            await self.app(scope, receive, send)
        finally:
            _hub_ctx_stack.pop()
from .middleware import base_auth_backend
from .config import (
    SERVICE_DEBUG, SERVICE_PORT, SERVICE_LOG_LEVEL, SERVICE_HOST,
    SERVICE_PRIVATE_KEY_PATH, SERVICE_PUBLIC_KEY_PATH,
    SERVICE_LOOP, SERVICE_HTTP,
    SERVICE_LIMIT_CONCURRENCY, SERVICE_LIMIT_MAX_REQUESTS,
    SERVICE_TIMEOUT_KEEP_ALIVE, SERVICE_BACKLOG,
    MIDDLEWARE_SESSION_ENABLED, MIDDLEWARE_AUTH_ENABLED, MIDDLEWARE_CORS_ENABLED,
    MIDDLEWARE_SESSION_SECRET_KEY,
)

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

    def __init__(self, web_app=None, router_mapping=None, **kwargs):
        super().__init__(**kwargs)
        self.app = self
        self.http_app = web_app or Starlette()
        self.uvicorn = None
        self.router_mapping = router_mapping or {}
        self.middlewares = self._build_middlewares()

    @staticmethod
    def _build_middlewares():
        mws = []
        if MIDDLEWARE_SESSION_ENABLED:
            mws.append(Middleware(SessionMiddleware, secret_key=MIDDLEWARE_SESSION_SECRET_KEY))
        if MIDDLEWARE_AUTH_ENABLED:
            mws.append(Middleware(AuthenticationMiddleware, backend=base_auth_backend))
        if MIDDLEWARE_CORS_ENABLED:
            mws.append(Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], max_age=1728000))
        return mws

    # async def on_first_start(self) -> None:
    #     self.exit_stack.enter_context(redirect_stdouts(self.logger))

    @staticmethod
    def _collect_router_mappings(service, visited=None):
        if visited is None: visited = set()
        if id(service) in visited: return {}
        visited.add(id(service))
        rm = dict(getattr(service, 'router_mapping', None) or {})
        for child in getattr(service, '_children', []):
            rm.update(HttpService._collect_router_mappings(child, visited))
        return rm

    async def on_start(self) -> None:
        merged = {}
        for app in hub.apps.values():
            merged.update(self._collect_router_mappings(app))
        merged.update(self.router_mapping)
        for key, command_cls in BaseCommand._registry.items():
            alias = command_cls.alias
            route = merged.get(command_cls.__name__, merged.get(alias, merged.get(key)))
            if route is None:
                continue
            methods = route[0] if len(route) > 0 else 'GET'
            methods = [methods] if isinstance(methods, str) else methods
            path = route[1] if len(route) > 1 else None
            if not path:
                domain = command_cls.destination.split('.')[0] if command_cls.destination else None
                path = f'/api/{domain}/{alias}' if domain else f'/api/{alias}'
            if 'SSE' in methods:
                methods = ['GET']
                handler = SseHandler(command_cls)
            else:
                handler = HttpHandler(command_cls)
            self.http_app.router.add_route(path, handler, methods=methods, name=alias, include_in_schema=True)
        self.http_app.user_middleware = self.middlewares
        self.http_app.debug = SERVICE_DEBUG
        self._asgi_app = HubContextMiddleware(self.http_app, hub._get_current_object())
        self.init_server()
        await super(HttpService, self).on_start()

    async def on_started(self) -> None:
        scheme = 'https' if SERVICE_PRIVATE_KEY_PATH else 'http'
        base = f'{scheme}://{SERVICE_HOST}:{SERVICE_PORT}'
        routes = [r for r in self.http_app.routes if hasattr(r, 'path')]
        lines = '\n  '.join(f'{",".join(r.methods)} {base}{r.path} -> {r.name}' for r in routes)
        self.logger.info(f'http({len(routes)} routes) {base}\n  {lines}')
        await super(HttpService, self).on_started()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(
            host=SERVICE_HOST,
            app=self._asgi_app,
            port=int(SERVICE_PORT),
            log_level=SERVICE_LOG_LEVEL,
            ssl_keyfile=SERVICE_PRIVATE_KEY_PATH,
            ssl_certfile=SERVICE_PUBLIC_KEY_PATH,
            loop=SERVICE_LOOP,
            http=SERVICE_HTTP,
            limit_concurrency=SERVICE_LIMIT_CONCURRENCY,
            limit_max_requests=SERVICE_LIMIT_MAX_REQUESTS,
            timeout_keep_alive=SERVICE_TIMEOUT_KEEP_ALIVE,
            backlog=SERVICE_BACKLOG
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
