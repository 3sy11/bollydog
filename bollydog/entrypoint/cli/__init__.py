import asyncio
import json
import logging
import os
import pathlib
import sys
from typing import Dict
import environs
import fire
from mode.utils.imports import smart_import
from ptpython.repl import embed

logging.info(f'load .env from {os.getcwd()}')
environs.Env().read_env(os.getcwd() + '/.env', recurse=False, verbose=True)

from bollydog.patch import yaml
from bollydog.bootstrap import Bootstrap
from bollydog.globals import _hub_ctx_stack, _protocol_ctx_stack
from bollydog.models.service import AppService
from bollydog.models.base import BaseCommand
from bollydog.service.config import BOLLYDOG_HTTP_ENABLED, BOLLYDOG_WS_ENABLED
from bollydog.service.app import Hub
from bollydog.entrypoint.http.app import HttpService
from bollydog.entrypoint.websocket.app import SocketService


def _load_config(config: str) -> Dict:
    if not config:
        return {}
    if config[-5:] == '.json':
        return json.loads(config)
    elif config[-5:] == '.yaml' or config[-4:] == '.yml':
        with open(config) as f:
            return yaml.safe_load(f)
    else:
        return smart_import(config)


def get_apps(config: str = None) -> Dict[str, AppService]:
    apps = {}
    if config:
        work_dir = pathlib.Path(config).parent
        sys.path.insert(0, work_dir.as_posix())
        for domain, app_config in (_load_config(config) or {}).items():
            if domain in apps:
                raise ValueError(f'duplicate domain: {domain}')
            app = app_config.pop('app')
            apps[domain] = app.create_from(**app_config)
    if BOLLYDOG_HTTP_ENABLED:
        apps['http'] = HttpService.create_from()
    if BOLLYDOG_WS_ENABLED:
        apps['ws'] = SocketService.create_from()
    return apps


class CLI:

    @staticmethod
    def service(config: str = None, apps: list = None):
        _apps = get_apps(config)
        if apps:
            _apps = {k: v for k, v in _apps.items() if k in apps}
        hub = Hub(apps=_apps.values())
        worker = Bootstrap(hub, override_logging=False)
        raise worker.execute_from_commandline()

    @staticmethod
    def ls(config: str = None):
        _base_fields = set(BaseCommand.model_fields.keys())
        alias_count: Dict[str, list] = {}
        for fqn, cmd_cls in BaseCommand._registry.items():
            alias_count.setdefault(cmd_cls.alias, []).append(fqn)
        rows = []
        for fqn, cmd_cls in BaseCommand._registry.items():
            name = cmd_cls.alias if len(alias_count[cmd_cls.alias]) == 1 else fqn
            dest = cmd_cls.destination or '-'
            user_fields = {k: v for k, v in cmd_cls.model_fields.items() if k not in _base_fields}
            params = ', '.join(f'{k}: {v.annotation.__name__}' for k, v in user_fields.items()) if user_fields else '-'
            rows.append((name, dest, params))
        if not rows:
            print('No commands registered.')
            return
        w0 = max(len(r[0]) for r in rows)
        w1 = max(len(r[1]) for r in rows)
        header = f'{"COMMAND":<{w0}}  {"DESTINATION":<{w1}}  PARAMS'
        print(header)
        print('-' * len(header))
        for name, dest, params in rows:
            print(f'{name:<{w0}}  {dest:<{w1}}  {params}')

    @staticmethod
    def execute(command: str, **kwargs):
        config = kwargs.pop('config', None)
        apps = get_apps(config)
        hub = Hub(apps=apps.values())
        cmd = BaseCommand.resolve(command)
        msg = cmd(**kwargs)
        logging.info(f'{msg.trace_id[:2]}{msg.parent_span_id[:2]}:{msg.span_id[:2]} prepare {msg.alias}')

        async def _run():
            async with hub:
                await hub.execute(msg)

        asyncio.run(_run())
        logging.info(json.dumps(msg.model_dump(), ensure_ascii=False))

    @staticmethod
    def shell(config: str = None):
        apps = get_apps(config)
        hub = Hub(apps=apps.values())
        for key, cmd_cls in BaseCommand._registry.items():
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
