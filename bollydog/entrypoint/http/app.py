from typing import Type
import logging
import mode
import uvicorn
from bollydog.models.service import AppService
# from bollydog.patch.logging import redirect_stdouts
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse

from bollydog.globals import hub, _session_ctx_stack
from bollydog.models.base import BaseMessage, get_model_name, Session
from bollydog.service.handler import AppHandler
from .config import (
    SERVICE_DEBUG,
    SERVICE_PORT,
    SERVICE_LOG_LEVEL,
    SERVICE_HOST,
    SERVICE_PRIVATE_KEY_PATH,
    SERVICE_PUBLIC_KEY_PATH,
    SERVICE_WORKERS,
    SERVICE_LOOP,
    SERVICE_HTTP,
    SERVICE_LIMIT_CONCURRENCY,
    SERVICE_LIMIT_MAX_REQUESTS,
    SERVICE_TIMEOUT_KEEP_ALIVE,
    SERVICE_BACKLOG
)

_config_middleware_key = 'middleware'


class HttpHandler:

    def __init__(self, message: Type[BaseMessage]):
        self.message = message

    async def __call__(self, scope, receive, send):
        request = Request(scope, receive=receive, send=send)
        with _session_ctx_stack.push(Session(username=scope['user'].display_name)):
            try:
                if request.method == 'GET':
                    message: BaseMessage = self.message(**request.query_params, **request.path_params)  # < 入参校验
                elif request.method == 'POST':
                    data = await request.json() or await request.form()
                    message: BaseMessage = self.message(**data, **request.path_params)  # < 入参校验
                else:
                    raise NotImplementedError
                message = await hub.put_message(message)
                result = await message.state  # ? 对future.result的异常做处理
            except Exception as e:
                result = {'error': str(e)}
                logging.error(e)
            if isinstance(result, str):
                response = HTMLResponse(result)
            else:
                response = JSONResponse(result)
            await response(scope, receive, send)


class HttpService(AppService):

    def __init__(self, web_app=None, router_mapping=None, middlewares=None, **kwargs):
        super().__init__(**kwargs)
        self.app = self
        self.http_app = web_app or Starlette()
        self.uvicorn = None
        self.router_mapping = router_mapping or {}
        self.middlewares = []
        for m in middlewares or []:
            self.middlewares.append(Middleware(m.pop(_config_middleware_key), **m))

    # async def on_first_start(self) -> None:
    #     self.exit_stack.enter_context(redirect_stdouts(self.logger))

    async def on_start(self) -> None:
        for message_model,handler in AppHandler.commands.items():
            entrypoint=f'{handler.app.name}.{message_model.name}'
            _methods = self.router_mapping.get(entrypoint, ['GET'])
            if isinstance(_methods, str):
                _methods = [_methods]
            self.http_app.router.add_route(
                f'/' + entrypoint.replace('.', '/'),
                HttpHandler(message_model),
                methods=_methods,
                name=None,
                include_in_schema=True,
            )
        for r in self.http_app.routes:
            self.logger.info(r)
        self.http_app.user_middleware = self.middlewares
        self.http_app.debug = SERVICE_DEBUG
        self.init_server()
        await super(HttpService, self).on_start()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(
            host=SERVICE_HOST,
            app=self.http_app,
            port=int(SERVICE_PORT),
            log_level=SERVICE_LOG_LEVEL,
            ssl_keyfile=SERVICE_PRIVATE_KEY_PATH,
            ssl_certfile=SERVICE_PUBLIC_KEY_PATH,
            workers=SERVICE_WORKERS,
            loop=SERVICE_LOOP,
            http=SERVICE_HTTP,
            limit_concurrency=SERVICE_LIMIT_CONCURRENCY,
            limit_max_requests=SERVICE_LIMIT_MAX_REQUESTS,
            timeout_keep_alive=SERVICE_TIMEOUT_KEEP_ALIVE,
            backlog=SERVICE_BACKLOG
        )
        self.uvicorn = uvicorn.Server(config)

    def http_app(self):
        """
        use case:
        uvicorn web.base.HttpService:app --reload
        :return:
        """
        self.init_server()
        return self.http_app

    async def on_stop(self) -> None:
        try:
            await self.uvicorn.shutdown()
        except Exception as e:
            self.logger.error(e)
        await super(HttpService, self).on_stop()
