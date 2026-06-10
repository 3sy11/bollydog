import asyncio
import json
import logging
import os
import sys
from typing import Dict

import environs
import fire
from ptpython.repl import embed

from bollydog.bootstrap import Bootstrap
from bollydog.entrypoint.uds.app import UdsService
from bollydog.entrypoint.uds.config import ENTRYPOINT_UDS_SEND_DEFAULT_CONFIG
from bollydog.globals import apps as _apps_proxy
from bollydog.models.base import BaseCommand
from bollydog.models.service import BaseService
from bollydog.service import parse_config, build_services

logging.info(f'load .env from {os.getcwd()}')
environs.Env().read_env(os.getcwd() + '/.env', recurse=False, verbose=True)


def _resolve_command(name: str):
    """CLI-level fuzzy resolve: exact -> suffix -> case-insensitive, with hints on ambiguity."""
    registry = BaseService.registry
    if name in registry: return registry[name]
    matches = {k: v for k, v in registry.items() if k.endswith(f'.{name}')}
    if len(matches) == 1: return next(iter(matches.values()))
    if len(matches) > 1: raise KeyError(f"Ambiguous '{name}', candidates: {list(matches.keys())}")
    nl = name.lower()
    matches = {k: v for k, v in registry.items() if v.alias.lower() == nl}
    if len(matches) == 1: return next(iter(matches.values()))
    if len(matches) > 1: raise KeyError(f"Ambiguous '{name}', candidates: {list(matches.keys())}")
    raise KeyError(f"Command '{name}' not found. Use `bollydog ls` to see available commands.")


class CLI:

    @staticmethod
    def service(config: str = None, domains: list = None):
        if config:
            sys.path.insert(0, os.path.dirname(os.path.abspath(config)))
        parsed = parse_config(config)
        apps = build_services(parsed, mode='service')
        hub = apps['bollydog.HubService']
        bootstrap = Bootstrap(hub, apps=apps, override_logging=False)
        if domains: bootstrap._domains = set(domains)
        bootstrap.execute_from_commandline()

    @staticmethod
    def ls(config: str = None):
        if config:
            sys.path.insert(0, os.path.dirname(os.path.abspath(config)))
        parsed = parse_config(config)
        apps = build_services(parsed, mode='service')
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
    def execute(command: str, timeout: int = 300, **kwargs):
        """Execute a single command. timeout is unified into message.expire_time."""
        config = kwargs.pop('config', None)
        if config:
            sys.path.insert(0, os.path.dirname(os.path.abspath(config)))
        parsed = parse_config(config)
        build_services(parsed, mode='execute')
        cmd_cls = _resolve_command(command)
        msg = cmd_cls(**kwargs)
        logging.info(f'{msg.trace_id[:2]}{msg.parent_span_id[:2]}:{msg.span_id[:2]} prepare {msg.alias}')
        apps = build_services(parsed, mode='execute')
        executor = apps['bollydog.ExecuteService']
        bootstrap = Bootstrap(executor, apps=apps, override_logging=False)
        bootstrap.run_once(msg, timeout=timeout)

    @staticmethod
    def send(command: str, socket: str, **kwargs):
        config = kwargs.pop('config', ENTRYPOINT_UDS_SEND_DEFAULT_CONFIG)
        if config:
            sys.path.insert(0, os.path.dirname(os.path.abspath(config)))
        parsed = parse_config(config)
        apps = build_services(parsed, mode='service')
        cmd_cls = _resolve_command(command)
        uds = UdsService(sock_path=socket)
        resp = asyncio.run(uds.send(cmd_cls.destination, kwargs))
        logging.info(json.dumps(resp, ensure_ascii=False))

    @staticmethod
    def shell(config: str = None):
        if config:
            sys.path.insert(0, os.path.dirname(os.path.abspath(config)))
        parsed = parse_config(config)
        apps = build_services(parsed, mode='service')
        hub = apps['bollydog.HubService']
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
