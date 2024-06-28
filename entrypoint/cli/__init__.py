import asyncio
import json
import logging
from typing import Dict

import fire
import yaml
from bootstrap import Bootstrap
from models.service import AppService
from mode.utils.imports import smart_import

from globals import _protocol_ctx_stack  # # noqa
from models.base import ModulePathWithDot, MessageName
from service.app import BusService, maybe_continue
from service.message import MessageManager


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
        return asyncio.run(maybe_continue(message=message, protocol=protocol))


def main():
    fire.Fire(CLI)


if __name__ == '__main__':
    main()
