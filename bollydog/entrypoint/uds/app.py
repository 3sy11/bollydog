import asyncio
import json
import os

import mode

from bollydog.entrypoint.uds.config import SOCK_PATH
from bollydog.globals import hub
from bollydog.models.base import BaseCommand
from bollydog.models.service import AppService


async def _read_frame(reader):
    raw = await reader.readexactly(4)
    n = int.from_bytes(raw, 'big')
    return (await reader.readexactly(n)).decode()


def _write_frame(writer, payload: str):
    data = payload.encode()
    writer.write(len(data).to_bytes(4, 'big') + data)


class UdsService(AppService):

    def __init__(self, sock_path=None, **kwargs):
        super().__init__(**kwargs)
        self._sock_path = sock_path or SOCK_PATH
        self._server = None

    async def send(self, command: str, kwargs: dict) -> dict:
        """Client: length-prefixed JSON; server resolves command and hub.dispatch(msg)."""
        reader, writer = await asyncio.open_unix_connection(self._sock_path)
        try:
            req = json.dumps({'command': command, 'kwargs': kwargs or {}})
            _write_frame(writer, req)
            await writer.drain()
            resp_raw = await _read_frame(reader)
            return json.loads(resp_raw)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def on_start(self) -> None:
        if os.path.exists(self._sock_path):
            try:
                os.unlink(self._sock_path)
            except OSError as e:
                self.logger.warning(f'uds unlink stale sock: {e}')
        self._server = await asyncio.start_unix_server(self._handle, path=self._sock_path)
        await super().on_start()

    async def on_started(self) -> None:
        self.logger.info(f'uds unix://{self._sock_path}')
        await super().on_started()

    @mode.task
    async def run_server(self):
        if self._server:
            await self._server.serve_forever()

    async def _handle(self, reader, writer):
        try:
            data = await _read_frame(reader)
            req = json.loads(data)
            cmd_cls = BaseCommand.resolve(req['command'])
            msg = cmd_cls(**req.get('kwargs', {}))
            msg = await hub.dispatch(msg)
            await msg.state
            resp = json.dumps({'status': 'ok', 'result': msg.model_dump()}, default=str)
        except Exception as e:
            self.logger.exception(e)
            resp = json.dumps({'status': 'error', 'error': str(e)})
        _write_frame(writer, resp)
        try:
            await writer.drain()
        except Exception:
            pass
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    async def on_stop(self) -> None:
        if self._server:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception as e:
                self.logger.error(e)
            self._server = None
        if os.path.exists(self._sock_path):
            try:
                os.unlink(self._sock_path)
            except OSError as e:
                self.logger.warning(f'uds unlink on stop: {e}')
        await super().on_stop()
