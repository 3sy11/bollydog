import asyncio
import json
import logging
import os
import pathlib
import sys
import tomllib
from typing import Dict
import environs
import fire
from mode.utils.imports import smart_import
from ptpython.repl import embed

logging.info(f'load .env from {os.getcwd()}')
environs.Env().read_env(os.getcwd() + '/.env', recurse=False, verbose=True)

from bollydog.bootstrap import Bootstrap
from bollydog.models.service import AppService, BaseService
from bollydog.models.base import BaseCommand
from bollydog.service.config import BOLLYDOG_HTTP_ENABLED, BOLLYDOG_WS_ENABLED, BOLLYDOG_UDS_ENABLED
from bollydog.service.app import Hub
from bollydog.entrypoint.http.app import HttpService
from bollydog.entrypoint.websocket.app import SocketService
from bollydog.entrypoint.uds.config import SEND_DEFAULT_CONFIG


def _load_config(config: str) -> Dict:
    if not config: return {}
    with open(config, 'rb') as f:
        return tomllib.load(f)


def get_apps(config: str = None) -> Dict[str, AppService]:
    apps = {}
    if config:
        work_dir = pathlib.Path(config).parent
        sys.path.insert(0, work_dir.as_posix())
        for node_name, node_conf in _load_config(config).items():
            cls = smart_import(node_name)
            svc = cls.create_from(**node_conf)
            domain = getattr(svc, 'domain', node_name)
            if domain in apps: raise ValueError(f'duplicate domain: {domain}')
            apps[domain] = svc
    if BOLLYDOG_HTTP_ENABLED:
        apps['http'] = HttpService.create_from()
    if BOLLYDOG_WS_ENABLED:
        apps['ws'] = SocketService.create_from()
    if BOLLYDOG_UDS_ENABLED:
        from bollydog.entrypoint.uds.app import UdsService
        apps['uds'] = UdsService.create_from()
    return apps


class CLI:

    @staticmethod
    def service(config: str = None, apps: list = None):
        _apps = get_apps(config)
        if apps: _apps = {k: v for k, v in _apps.items() if k in apps}
        hub = Hub(apps=_apps.values())
        worker = Bootstrap(hub, override_logging=False)
        raise worker.execute_from_commandline()

    @staticmethod
    def ls(config: str = None):
        get_apps(config)
        registry = BaseService.registry
        _base_fields = set(BaseCommand.model_fields.keys())
        alias_count: Dict[str, list] = {}
        for fqn, cmd_cls in registry.items():
            alias_count.setdefault(cmd_cls.alias, []).append(fqn)
        rows = []
        for fqn, cmd_cls in registry.items():
            name = cmd_cls.alias if len(alias_count[cmd_cls.alias]) == 1 else fqn
            topic = cmd_cls.destination or '-'
            user_fields = {k: v for k, v in cmd_cls.model_fields.items() if k not in _base_fields}
            params = ', '.join(f'{k}: {v.annotation.__name__}' for k, v in user_fields.items()) if user_fields else '-'
            rows.append((name, topic, params))
        if not rows:
            print('No commands registered.')
            return
        w0 = max(len(r[0]) for r in rows)
        w1 = max(len(r[1]) for r in rows)
        header = f'{"COMMAND":<{w0}}  {"TOPIC":<{w1}}  PARAMS'
        print(header)
        print('-' * len(header))
        for name, topic, params in rows:
            print(f'{name:<{w0}}  {topic:<{w1}}  {params}')

    @staticmethod
    def execute(command: str, **kwargs):
        config = kwargs.pop('config', None)
        apps = get_apps(config)
        hub = Hub(apps=apps.values())
        cmd = BaseService.registry.resolve(command)
        msg = cmd(**kwargs)
        logging.info(f'{msg.trace_id[:2]}{msg.parent_span_id[:2]}:{msg.span_id[:2]} prepare {msg.alias}')

        async def _run():
            async with hub:
                await hub.execute(msg)

        asyncio.run(_run())
        logging.info(json.dumps(msg.model_dump(), ensure_ascii=False))

    @staticmethod
    def send(command: str, socket: str, **kwargs):
        config = kwargs.pop('config', SEND_DEFAULT_CONFIG)
        get_apps(config)
        cmd_cls = BaseService.registry.resolve(command)
        cmd_cls(**kwargs)
        from bollydog.entrypoint.uds.app import UdsService
        uds = UdsService(sock_path=socket)
        resp = asyncio.run(uds.send(command, kwargs))
        logging.info(json.dumps(resp, ensure_ascii=False))

    @staticmethod
    def shell(config: str = None):
        apps = get_apps(config)
        hub = Hub(apps=apps.values())
        for key, cmd_cls in BaseService.registry.items():
            print(f'{key} -> {cmd_cls}')
        ns = {**globals(), 'apps': apps, 'hub': hub, 'BaseCommand': BaseCommand}

        async def _run():
            async with hub:
                await embed(ns, ns, return_asyncio_coroutine=True, history_filename='.ptpython.tmp', patch_stdout=True)

        asyncio.run(_run())


def main():
    fire.Fire(CLI)


if __name__ == '__main__':
    main()
