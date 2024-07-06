import pathlib

import sys
sys.path.append(pathlib.Path(__file__).parent.parent.parent.as_posix())
print(sys.path)

import pytest
from bollydog.service.model import TaskCount, TaskList
from bollydog.patch import yaml

from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient

from bollydog.service.app import BusService

path = pathlib.Path(__file__).parent.parent.joinpath('./config.yml')


@pytest.mark.asyncio
async def test_run_service():
    with open(path.as_posix()) as f:
        config = yaml.safe_load(f)
    apps = {}
    for app_name, app_config in config.items():
        app = app_config['app']
        apps[app_name] = app.create_from(**app_config)

    bus = BusService.create_from(apps=apps.values())

    async with bus:
        m1 = TaskCount()
        m2 = TaskList()
        await bus.put_message(m1)
        # await asyncio.sleep(1)
        r1 = await m1.state
        await bus.put_message(m2)
        # await asyncio.sleep(1)
        r2 = await m2.state
        assert r1
        assert r2
        web_service = bus.apps.get('http')
        web_app = web_service.http_app
        async with AsyncClient(transport=ASGITransport(app=web_app), base_url="http://0.0.0.0") as client:
            r1 = await client.get('/bollydog/service/model/TaskList', timeout=1)
            assert r1.status_code == 200
            r2 = await client.get('/bollydog/service/model/TaskCount', timeout=1)
            assert r2.status_code == 200

        client = TestClient(bus.apps.get('websocket').socket_app)
        with client.websocket_connect('/') as ws:
            ws.send_text('{"name":"bollydog.service.model.TaskCount"}')
        bus.supervisor = None
