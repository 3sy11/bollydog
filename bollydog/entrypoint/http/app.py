from typing import Type

import mode
import uvicorn
from bollydog.models.service import AppService
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse

from bollydog.globals import bus, _session_ctx_stack
from bollydog.models.base import BaseMessage, get_model_name, Session
from .config import (
    SERVICE_DEBUG,
    SERVICE_PORT,
    SERVICE_LOG_LEVEL,
    SERVICE_HOST,
    SERVICE_PRIVATE_KEY_PATH,
    SERVICE_PUBLIC_KEY_PATH
)

_config_middleware_key = 'middleware'


class CommandHandler:

    def __init__(self, message: Type[BaseMessage]):
        self.message = message

    async def __call__(self, scope, receive, send):
        request = Request(scope, receive=receive, send=send)
        with _session_ctx_stack.push(Session(username=scope['user'].display_name)):
            try:
                message: BaseMessage = self.message(**request.query_params)  # < 入参校验
                message = await bus.put_message(message)
                result = await message.state  # ? 对future.result的异常做处理
            except Exception as e:
                result = {'error': str(e)}
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

    async def on_start(self) -> None:
        for message_model in bus.app_handler.handlers.keys():
            message_model_name = get_model_name(message_model)
            _methods = self.router_mapping.get(message_model_name, ['GET'])
            if isinstance(_methods, str):
                _methods = [_methods]
            self.http_app.router.add_route(
                '/' + message_model_name.replace('.', '/'),
                CommandHandler(message_model),
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
            ssl_certfile=SERVICE_PUBLIC_KEY_PATH
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
