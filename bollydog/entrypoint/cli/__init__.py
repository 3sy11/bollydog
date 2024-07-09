import asyncio
import json
import logging
import pathlib
import sys
from typing import Dict, Coroutine
from ptpython.repl import embed
import fire
import environs
from bollydog.bootstrap import Bootstrap
from bollydog.models.service import AppService
from bollydog.patch import yaml
from mode.utils.imports import smart_import

from bollydog.globals import _bus_ctx_stack  # # noqa
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
    work_dir = pathlib.Path(config).parent
    logging.info(
        f'loading env from {work_dir.as_posix()}:{environs.Env().read_env(work_dir.joinpath(".env").as_posix())}'
    )
    sys.path.insert(0, work_dir.as_posix())
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
            config: str,
            message: MessageName,
            app: str = None,
            handler: ModulePathWithDot = None,
            **kwargs
    ):
        apps = get_apps(config)
        app = app or message.split('.')[0]
        app = apps[app]
        bus = BusService.create_from(apps=apps.values())
        with _bus_ctx_stack.push(bus):
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
            exclude: list = None,
            include: list = None
    ):
        apps = get_apps(config)
        if exclude:
            for app_name in exclude:
                apps.pop(app_name)
        if include:
            apps = {k: v for k, v in apps.items() if k in include}
        bus = BusService.create_from(apps=apps.values())
        worker = Bootstrap(bus)
        raise worker.execute_from_commandline()

    @staticmethod
    def execute(config: str, message: MessageName, app: str = None, **kwargs):
        apps = get_apps(config)
        app = app or message.split('.')[0]
        protocol = apps[app]
        bus = BusService.create_from(apps=apps.values())

        async def _execute():
            with _bus_ctx_stack.push(bus):
                msg = smart_import(message)
                tasks = MessageManager.create_tasks(msg, protocol)
                await MessageManager.wait_many(tasks)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_execute())

    @staticmethod
    def shell(config: str, ):
        apps = get_apps(config)
        bus = BusService.create_from(apps=apps.values())
        mm = MessageManager
        print(mm.messages)
        print(mm.handlers)
        embed_result: Coroutine = embed(globals(), locals(), return_asyncio_coroutine=True)  # # noqa
        # print("Starting ptpython asyncio REPL")
        # print('Use "await" directly instead of "asyncio.run()".')
        asyncio.run(embed_result)


def main():
    fire.Fire(CLI)


if __name__ == '__main__':
    main()
