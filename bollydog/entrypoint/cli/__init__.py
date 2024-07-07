import asyncio
import json
import logging
import pathlib
import sys
from typing import Dict, Coroutine
from ptpython.repl import embed
import fire
from bollydog.bootstrap import Bootstrap
from bollydog.models.service import AppService
from bollydog.patch import yaml
from mode.utils.imports import smart_import

from bollydog.globals import _protocol_ctx_stack  # # noqa
from bollydog.models.base import ModulePathWithDot, MessageName
from bollydog.service.app import BusService
from bollydog.service.message import MessageManager


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


def get_apps(config: str) -> Dict[str, AppService]:
    config = _load_config(config)
    apps = {}
    for app_name, app_config in config.items():
        app = app_config.pop('app')
        apps[app_name] = app.create_from(**app_config)
    return apps


class CLI:

    # # 入参如果是字符串，需要做一次转义或者使用单引号，例如：'"str"',"'str'",\"str\"
    @staticmethod
    def command(
            app: str,
            config: str,
            message: MessageName,
            handler: ModulePathWithDot = None,
            **kwargs
    ):
        apps = get_apps(config)
        app = apps[app]
        message = MessageManager.messages[message](**kwargs)
        if handler:
            handlers = [smart_import(handler)]
        else:
            handlers = [MessageManager.handlers[h] for h in MessageManager.mapping[message.name]]

        for handler in handlers:
            result = asyncio.run(handler(message, protocol=app.protocol))
            logging.info(result)

    @staticmethod
    def service(
            config: str,
            app: str = None,
            only: str = None,
    ):
        if app and only:
            raise ValueError('only one of app and only can be set')
        config = _load_config(config)
        apps = {}
        if app:
            app = smart_import(app)
            apps[app.__name__] = app.create_from(config=config)
        else:
            for app_name, app_config in config.items():
                app = app_config.pop('app')
                apps[app_name] = app.create_from(**app_config)
        if only:
            worker = Bootstrap(apps[only])
        else:
            bus = BusService.create_from(apps=apps.values())
            worker = Bootstrap(bus)
        raise worker.execute_from_commandline()

    @staticmethod
    def execute(message: ModulePathWithDot, config: str = None, app: str = None):
        protocol = None
        if config:
            protocol = get_apps(config)[app]
        message = smart_import(message)
        tasks = MessageManager.create_tasks(message, protocol)
        return MessageManager.wait_many(tasks)

    @staticmethod
    def shell(config: str,):
        path = pathlib.Path(config).parent.as_posix()
        sys.path.insert(0, path)
        apps = get_apps(config)
        bus = BusService.create_from(apps=apps.values())
        mm = MessageManager
        embed_result:Coroutine=embed(globals(), locals(), return_asyncio_coroutine=True)  # # noqa
        print("Starting ptpython asyncio REPL")
        print('Use "await" directly instead of "asyncio.run()".')
        asyncio.run(embed_result)


def main():
    fire.Fire(CLI)


if __name__ == '__main__':
    main()
