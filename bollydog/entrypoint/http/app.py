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

from bollydog.globals import hub, apps as _apps_proxy, _hub_ctx_stack
from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService, BaseService

from .config import (
    ENTRYPOINT_HTTP_SERVICE_DEBUG, ENTRYPOINT_HTTP_SERVICE_PORT, ENTRYPOINT_HTTP_SERVICE_LOG_LEVEL, ENTRYPOINT_HTTP_SERVICE_HOST,
    ENTRYPOINT_HTTP_SERVICE_PRIVATE_KEY_PATH, ENTRYPOINT_HTTP_SERVICE_PUBLIC_KEY_PATH,
    ENTRYPOINT_HTTP_SERVICE_LOOP, ENTRYPOINT_HTTP_SERVICE_HTTP,
    ENTRYPOINT_HTTP_SERVICE_LIMIT_CONCURRENCY, ENTRYPOINT_HTTP_SERVICE_LIMIT_MAX_REQUESTS,
    ENTRYPOINT_HTTP_SERVICE_TIMEOUT_KEEP_ALIVE, ENTRYPOINT_HTTP_SERVICE_BACKLOG,
    ENTRYPOINT_HTTP_MIDDLEWARE_SESSION, ENTRYPOINT_HTTP_MIDDLEWARE_AUTH, ENTRYPOINT_HTTP_MIDDLEWARE_CORS,
    ENTRYPOINT_HTTP_MIDDLEWARE_SESSIONS_SECRET_KEY,
)
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

    def __init__(self, web_app=None, **kwargs):
        super().__init__(**kwargs)
        self.app = self
        self.http_app = web_app or Starlette()
        self.uvicorn = None
        self.middlewares = self._build_middlewares()

    @staticmethod
    def _build_middlewares():
        mws = []
        if ENTRYPOINT_HTTP_MIDDLEWARE_SESSION:
            mws.append(Middleware(SessionMiddleware, secret_key=ENTRYPOINT_HTTP_MIDDLEWARE_SESSIONS_SECRET_KEY))
        if ENTRYPOINT_HTTP_MIDDLEWARE_AUTH:
            mws.append(Middleware(AuthenticationMiddleware, backend=base_auth_backend))
        if ENTRYPOINT_HTTP_MIDDLEWARE_CORS:
            mws.append(Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'], max_age=1728000))
        return mws

    # async def on_first_start(self) -> None:
    #     self.exit_stack.enter_context(redirect_stdouts(self.logger))

    @staticmethod
    def _collect_router_mappings(service, visited=None):
        if visited is None: visited = set()
        if id(service) in visited: return {}
        visited.add(id(service))
        rm = dict(service.router_mapping)
        for child in getattr(service, '_children', []):
            rm.update(HttpService._collect_router_mappings(child, visited))
        return rm

    async def on_start(self) -> None:
        merged = {}
        for app in _apps_proxy.values():
            merged.update(self._collect_router_mappings(app))
        for key, command_cls in BaseService.registry.items():
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
                if inspect.isasyncgenfunction(command_cls.__call__):
                    handler = SseHandler(command_cls)
                else:
                    logging.warning(f'{alias} mapped as SSE but is not async generator, falling back to HTTP')
                    handler = HttpHandler(command_cls)
            else:
                handler = HttpHandler(command_cls)
            self.http_app.router.add_route(path, handler, methods=methods, name=alias, include_in_schema=True)
        self.http_app.user_middleware = self.middlewares
        self.http_app.debug = ENTRYPOINT_HTTP_SERVICE_DEBUG
        self._asgi_app = HubContextMiddleware(self.http_app, hub._get_current_object())
        self.init_server()
        await super(HttpService, self).on_start()

    async def on_started(self) -> None:
        scheme = 'https' if ENTRYPOINT_HTTP_SERVICE_PRIVATE_KEY_PATH else 'http'
        base = f'{scheme}://{ENTRYPOINT_HTTP_SERVICE_HOST}:{ENTRYPOINT_HTTP_SERVICE_PORT}'
        routes = [r for r in self.http_app.routes if hasattr(r, 'path')]
        lines = '\n  '.join(f'{",".join(r.methods)} {base}{r.path} -> {r.name}' for r in routes)
        self.logger.info(f'http({len(routes)} routes) {base}\n  {lines}')
        await super(HttpService, self).on_started()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(
            host=ENTRYPOINT_HTTP_SERVICE_HOST,
            app=self._asgi_app,
            port=int(ENTRYPOINT_HTTP_SERVICE_PORT),
            log_level=ENTRYPOINT_HTTP_SERVICE_LOG_LEVEL,
            ssl_keyfile=ENTRYPOINT_HTTP_SERVICE_PRIVATE_KEY_PATH,
            ssl_certfile=ENTRYPOINT_HTTP_SERVICE_PUBLIC_KEY_PATH,
            loop=ENTRYPOINT_HTTP_SERVICE_LOOP,
            http=ENTRYPOINT_HTTP_SERVICE_HTTP,
            limit_concurrency=ENTRYPOINT_HTTP_SERVICE_LIMIT_CONCURRENCY,
            limit_max_requests=ENTRYPOINT_HTTP_SERVICE_LIMIT_MAX_REQUESTS,
            timeout_keep_alive=ENTRYPOINT_HTTP_SERVICE_TIMEOUT_KEEP_ALIVE,
            backlog=ENTRYPOINT_HTTP_SERVICE_BACKLOG
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
