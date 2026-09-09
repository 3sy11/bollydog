import json
from typing import Dict, Set

import mode
import uvicorn
from starlette.applications import Starlette
from starlette.websockets import WebSocket, WebSocketDisconnect

from bollydog.globals import hub, registry, _hub_ctx_stack
from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService


class SocketService(AppService):
    host: str = '0.0.0.0'
    port: int = 8001
    debug: bool = False
    log_level: str = 'info'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = self
        self.socket_app = Starlette()
        self.uvicorn = None
        self.clients: Set[WebSocket] = set()
        self.listening: Dict[str, Set[WebSocket]] = {}

    async def attach(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.add(websocket)
        self.logger.debug(f"client joined, total: {len(self.clients)}")

    async def detach(self, websocket: WebSocket):
        self.clients.discard(websocket)
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
        _hub_ctx_stack.push_without_automatic_cleanup(hub._get_current_object())
        await self.attach(websocket)
        try:
            while True:
                raw = json.loads(await websocket.receive_text())
                self.logger.debug(f"received: {raw}")
                name = raw.pop('name', None) or raw.pop('alias', None)
                try:
                    cmd_cls = registry.resolve(name) if name else None
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
            client = websocket.client
            self.logger.debug(f'ws disconnected: {client.host}:{client.port}' if client else 'ws disconnected')
        except Exception as e:
            self.logger.exception(e)
        finally:
            _hub_ctx_stack.pop()
            await self.detach(websocket)

    async def on_start(self) -> None:
        self.socket_app.add_websocket_route("/", self.websocket_endpoint)
        self.socket_app.debug = self.debug
        self.init_server()
        await super(SocketService, self).on_start()

    async def on_started(self) -> None:
        self.logger.info(f'ws ws://{self.host}:{self.port}/')
        await super(SocketService, self).on_started()

    @mode.task
    async def run_server(self):
        await self.uvicorn.serve()

    def init_server(self):
        config = uvicorn.Config(host=self.host, app=self.socket_app, port=int(self.port), log_level=self.log_level)
        self.uvicorn = uvicorn.Server(config)

    async def on_stop(self) -> None:
        for ws in list(self.clients):
            try: await ws.close()
            except Exception: pass
        try: await self.uvicorn.shutdown()
        except Exception as e: self.logger.error(e)
        await super(SocketService, self).on_stop()
