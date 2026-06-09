"""Service configuration loading: parse_config + build_services."""
import os

SKIP_IN_EXECUTE = {'bollydog.service.app.HubService', 'bollydog.service.exchange.Exchange', 'bollydog.service.queue.Queue'}


def parse_config(config: str = None) -> dict:
    """Pure function: read and merge TOML configs, no side effects."""
    import pathlib, tomllib
    hub_toml = pathlib.Path(__file__).parent / 'config.toml'
    with open(hub_toml, 'rb') as f:
        merged = tomllib.load(f)
    if config:
        with open(config, 'rb') as f:
            merged.update(tomllib.load(f))
    return merged


def build_services(parsed: dict, mode: str = 'service') -> None:
    """Instantiate services from parsed config dict.
    mode='service': full stack (HubService + Queue + Exchange + Session + entrypoints + all apps)
    mode='execute': minimal (ExecuteService + Session + user AppServices, skip Queue/Exchange/HubService/entrypoints)
    """
    import pathlib, sys
    from mode.utils.imports import smart_import
    from bollydog.models.service import AppService

    if mode == 'execute':
        for node_name, node_conf in parsed.items():
            if node_name in SKIP_IN_EXECUTE: continue
            node_conf = dict(node_conf)
            module = node_conf.pop('module', node_name)
            smart_import(module).create_from(**node_conf)
    else:
        for node_name, node_conf in parsed.items():
            node_conf = dict(node_conf)
            module = node_conf.pop('module', node_name)
            smart_import(module).create_from(**node_conf)
        from bollydog.entrypoint.http.app import HttpService
        from bollydog.entrypoint.uds.app import UdsService
        from bollydog.entrypoint.websocket.app import SocketService
        if os.getenv('ENTRYPOINT_HTTP_ENABLED', '0') == '1': HttpService.create_from()
        if os.getenv('ENTRYPOINT_WS_ENABLED', '0') == '1': SocketService.create_from()
        if os.getenv('ENTRYPOINT_UDS_ENABLED', '0') == '1': UdsService.create_from()

    for svc in list(AppService._apps.values()):
        resolved = []
        for dep_key in (svc.depends if isinstance(svc.depends, (list, tuple)) and svc.depends and isinstance(svc.depends[0], str) else []):
            dep = AppService._apps.get(dep_key)
            if dep is None: raise ValueError(f"depends '{dep_key}' not found for {svc.domain}.{svc.alias}")
            svc.add_dependency(dep)
            resolved.append(dep)
        if resolved: svc.depends = resolved
    for svc in AppService._apps.values():
        if type(svc).commands: type(svc)._load_commands(type(svc).commands)


def load_from_config(config: str = None) -> None:
    """Legacy wrapper: parse + build in service mode."""
    import sys, pathlib
    if config:
        work_dir = pathlib.Path(config).parent
        sys.path.insert(0, work_dir.as_posix())
    build_services(parse_config(config), mode='service')


__all__ = ['parse_config', 'build_services', 'load_from_config']
