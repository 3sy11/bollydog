"""CLI entry point for bollydog framework."""
import asyncio
import json
import logging
import os

import environs
import fire
from ptpython.repl import embed

from bollydog.bootstrap import Bootstrap
from bollydog.entrypoint.uds.app import UdsService
from bollydog.entrypoint.uds.config import ENTRYPOINT_UDS_SEND_DEFAULT_CONFIG
from bollydog.globals import registry
from bollydog.models.base import BaseCommand

environs.Env().read_env(os.getcwd() + '/.env', recurse=False, verbose=True)


class CLI:

    @staticmethod
    def service(config: str = None):
        Bootstrap(config=config, override_logging=False).run()

    @staticmethod
    def ls(config: str = None):
        bootstrap = Bootstrap(config=config, override_logging=False)
        commands = registry.commands
        _base_fields = set(BaseCommand.model_fields.keys())
        rows = []
        for destination, cmd_cls in commands.items():
            _user_fields = {k: v for k, v in cmd_cls.model_fields.items() if k not in _base_fields}
            _params = ', '.join(f'{k}: {v.annotation.__name__}' for k, v in _user_fields.items()) if _user_fields else '-'
            rows.append((cmd_cls.alias, destination, _params))
        if not rows:
            print('No commands registered.'); return
        _w0 = max(len(r[0]) for r in rows)
        _w1 = max(len(r[1]) for r in rows)
        print(f'{"COMMAND":<{_w0}}  {"DESTINATION":<{_w1}}  PARAMS')
        for cmd_alias, destination, params in rows:
            print(f'{cmd_alias:<{_w0}}  {destination:<{_w1}}  {params}')

    @staticmethod
    def execute(command: str, config: str, timeout: int = 300, **kwargs):
        """Execute a single command. config is required."""
        bootstrap = Bootstrap(config=config, override_logging=False)
        cmd_cls = registry.resolve(command)
        msg = cmd_cls(**kwargs)
        bootstrap.run(msg, timeout=timeout)

    @staticmethod
    def send(command: str, socket: str, config: str = ENTRYPOINT_UDS_SEND_DEFAULT_CONFIG, **kwargs):
        bootstrap = Bootstrap(config=config, override_logging=False)
        cmd_cls = registry.resolve(command)
        uds_service = UdsService(sock_path=socket)
        _resp = asyncio.run(uds_service.send(command, kwargs))
        logging.info(json.dumps(_resp, ensure_ascii=False))

    @staticmethod
    def shell(config: str = None):
        bootstrap = Bootstrap(config=config, override_logging=False)
        for destination, cmd_cls in registry.commands.items():
            print(f'{destination} -> {cmd_cls}')
        ns = {**globals(), 'services': bootstrap.services, 'hub': bootstrap.services.hub,
              'registry': registry, 'BaseCommand': BaseCommand}
        async def _run():
            async with bootstrap.services.hub:
                await embed(ns, ns, return_asyncio_coroutine=True, history_filename='.ptpython.tmp', patch_stdout=True)
        asyncio.run(_run())


def main():
    fire.Fire(CLI)


if __name__ == '__main__':
    main()
