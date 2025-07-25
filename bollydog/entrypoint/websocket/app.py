import json
from typing import Dict, Set

import mode
import uvicorn
from bollydog.models.service import AppService
from starlette.applications import Starlette
from starlette.websockets import WebSocket, WebSocketDisconnect

from bollydog.entrypoint.websocket.config import SERVICE_DEBUG, SERVICE_PORT, SERVICE_LOG_LEVEL, SERVICE_HOST
from bollydog.globals import hub
from bollydog.models.base import BaseMessage, MessageTraceId, Session


class SocketService(AppService):
    subscribers = set()
    listening: Dict[MessageTraceId, Set[WebSocket]] = {}
    sessions: Dict[Session, WebSocket] = {}

    async def subscribe(self, websocket: WebSocket):
        await websocket.accept()
        self.subscribers.add(websocket)
        self.logger.debug(f"New subscriber added, total subscribers: {len(self.subscribers)}")

    async def unsubscribe(self, websocket: WebSocket):  # < ping pong remove
        self.subscribers.remove(websocket)
        _ids = [_id for _id, ws in self.listening.items() if websocket in ws]
        for _id in _ids:
            self.listening[_id].remove(websocket)
            if not len(self.listening[_id]):
                self.listening.pop(_id)
        self.logger.debug(f"A subscriber unsubscribed, total subscribers: {len(self.subscribers)}")

    async def publish(self, message: BaseMessage):
        subscribers = self.listening.get(message.trace_id, [])
        for subscriber in subscribers:
            try:
                await message.state
                await subscriber.send_json(message.model_dump())
            except Exception as e:
                self.logger.exception(e)
                # await self.unsubscribe(subscriber)  # # raise set changed during iteration

    async def websocket_endpoint(self, websocket: WebSocket):
        await self.subscribe(websocket)  # < 鉴权
        try:
            while True:
                message = await websocket.receive_text()
                self.logger.debug(f"Received message from client: {message}")
                message = json.loads(message)
                if message['name'] in hub.app_handler.messages:
                    message = hub.app_handler.messages[message['name']](**message)
                else:
                    message = BaseMessage(**message)
                if message.trace_id in self.listening:
                    self.listening[message.trace_id].add(websocket)
                else:
                    self.listening[message.trace_id] = {websocket}
                await hub.put_message(message)
                await websocket.send_text(message.model_dump_json())
                await self.publish(message)  # < 或者改为再提交一个消息，上面的用于执行，这个用于获取结果的view消息

        except WebSocketDisconnect:
            self.logger.debug(f'websocket disconnected: {websocket.client.host}:{websocket.client.port}')
        except Exception as e:  # > 处理put_message的异常
            self.logger.error(e)
            # await self.unsubscribe(websocket)

    def __init__(self, socket_app=None, **kwargs):
        self.app = self
        self.socket_app = socket_app or Starlette()
        self.uvicorn = None
        super().__init__(**kwargs)

    async def on_first_start(self) -> None:
        hub.router.register('*', self.publish)  # ?

    async def on_start(self) -> None:
        self.socket_app.add_websocket_route("/", self.websocket_endpoint)
        self.socket_app.debug = SERVICE_DEBUG
        self.init_server()
        await super(SocketService, self).on_start()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(
            host=SERVICE_HOST,
            app=self.socket_app,
            port=int(SERVICE_PORT),
            log_level=SERVICE_LOG_LEVEL
        )
        self.uvicorn = uvicorn.Server(config)

    def web_app(self):
        """
        use case:
        uvicorn web.base.WebService:app --reload
        :return:
        """
        self.init_server()
        return self.socket_app

    async def on_stop(self) -> None:
        try:
            await self.uvicorn.shutdown()
        except Exception as e:
            self.logger.error(e)
        await super(SocketService, self).on_stop()
