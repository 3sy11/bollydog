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
        commands = registry.all_commands()
        if not commands:
            print('No commands registered.'); return

        rows = []
        for dest, cmd_cls in commands.items():
            desc = cmd_cls.describe()
            params = []
            for k, v in desc['parameters'].items():
                req = '*' if k in desc['required'] else ' '
                ptype = v.get('type', v.get('anyOf', 'any'))
                default = f'={v["default"]}' if 'default' in v else ''
                params.append(f'{req}{k}: {ptype}{default}')
            rows.append((desc['name'], dest, desc['description'], params))

        w_name = max(len(r[0]) for r in rows)
        w_dest = max(len(r[1]) for r in rows)
        header = f'{"COMMAND":<{w_name}}  {"DESTINATION":<{w_dest}}  DESCRIPTION / PARAMS'
        print(header)
        print('-' * len(header))
        indent = ' ' * (w_name + w_dest + 4)
        for name, dest, description, params in rows:
            print(f'{name:<{w_name}}  {dest:<{w_dest}}  {description or "-"}')
            for p in params:
                print(f'{indent}  {p}')

    @staticmethod
    def execute(command: str, config: str = None, timeout: int = 300, **kwargs):
        bootstrap = Bootstrap(config=config, override_logging=False)
        cmd_cls = registry.resolve(command)
        bootstrap.run(lambda: cmd_cls(**kwargs), timeout=timeout)

    @staticmethod
    def send(command: str, socket: str, config: str = None, **kwargs):
        # TODO: optimize startup — avoid full Bootstrap for send-only mode
        bootstrap = Bootstrap(config=config, override_logging=False)
        cmd_cls = registry.resolve(command)
        uds_service = UdsService()
        uds_service.sock_path = socket
        _resp = asyncio.run(uds_service.send(command, kwargs))
        logging.info(json.dumps(_resp, ensure_ascii=False))

    @staticmethod
    def shell(config: str = None):
        bootstrap = Bootstrap(config=config, override_logging=False)
        for destination, cmd_cls in registry.all_commands().items():
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
