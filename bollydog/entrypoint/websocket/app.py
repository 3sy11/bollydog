import json
from typing import Dict, Set

import mode
import uvicorn
from starlette.applications import Starlette
from starlette.websockets import WebSocket, WebSocketDisconnect

from bollydog.entrypoint.websocket.config import SERVICE_DEBUG, SERVICE_PORT, SERVICE_LOG_LEVEL, SERVICE_HOST
from bollydog.globals import hub
from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService


class SocketService(AppService):

    def __init__(self, socket_app=None, **kwargs):
        super().__init__(**kwargs)
        self.app = self
        self.socket_app = socket_app or Starlette()
        self.uvicorn = None
        self.subscribers: Set[WebSocket] = set()
        self.listening: Dict[str, Set[WebSocket]] = {}

    async def subscribe(self, websocket: WebSocket):
        await websocket.accept()
        self.subscribers.add(websocket)
        self.logger.debug(f"subscriber joined, total: {len(self.subscribers)}")

    async def unsubscribe(self, websocket: WebSocket):
        self.subscribers.discard(websocket)
        for trace_id in [k for k, ws in self.listening.items() if websocket in ws]:
            self.listening[trace_id].discard(websocket)
            if not self.listening[trace_id]:
                del self.listening[trace_id]

    async def _send_result(self, websocket: WebSocket, message: BaseCommand):
        message = await hub.dispatch(message)
        if message.is_async_gen:
            async for value in message.state:
                await websocket.send_json({'trace_id': message.trace_id, 'data': value})
        else:
            result = await message.state
            await websocket.send_json({'trace_id': message.trace_id, 'data': result})

    async def websocket_endpoint(self, websocket: WebSocket):
        await self.subscribe(websocket)
        try:
            while True:
                raw = json.loads(await websocket.receive_text())
                self.logger.debug(f"received: {raw}")
                name = raw.pop('name', None) or raw.pop('alias', None)
                try:
                    cmd_cls = BaseCommand.resolve(name) if name else None
                except KeyError:
                    await websocket.send_json({'error': f"command '{name}' not found"})
                    continue
                if not cmd_cls:
                    await websocket.send_json({'error': 'missing command name'})
                    continue
                username = getattr(websocket.scope.get('user'), 'display_name', None)
                message = cmd_cls(**raw, created_by=username)
                self.listening.setdefault(message.trace_id, set()).add(websocket)
                try:
                    await self._send_result(websocket, message)
                except Exception as e:
                    self.logger.error(e)
                    await websocket.send_json({'trace_id': message.trace_id, 'error': str(e)})
        except WebSocketDisconnect:
            self.logger.debug(f'ws disconnected: {websocket.client.host}:{websocket.client.port}')
        except Exception as e:
            self.logger.exception(e)
        finally:
            await self.unsubscribe(websocket)

    async def on_start(self) -> None:
        self.socket_app.add_websocket_route("/", self.websocket_endpoint)
        self.socket_app.debug = SERVICE_DEBUG
        self.init_server()
        await super(SocketService, self).on_start()

    async def on_started(self) -> None:
        self.logger.info(f'ws ws://{SERVICE_HOST}:{SERVICE_PORT}/')
        await super(SocketService, self).on_started()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(host=SERVICE_HOST, app=self.socket_app, port=int(SERVICE_PORT), log_level=SERVICE_LOG_LEVEL)
        self.uvicorn = uvicorn.Server(config)

    async def on_stop(self) -> None:
        for ws in list(self.subscribers):
            try: await ws.close()
            except Exception: pass
        try: await self.uvicorn.shutdown()
        except Exception as e: self.logger.error(e)
        await super(SocketService, self).on_stop()
