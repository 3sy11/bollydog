"""Deferred imports inside load_from_config to avoid circular import with models.base -> service.config."""
import os


def load_from_config(config: str = None) -> None:
    import pathlib, sys, tomllib
    from mode.utils.imports import smart_import
    from bollydog.models.service import AppService
    from bollydog.entrypoint.http.app import HttpService
    from bollydog.entrypoint.uds.app import UdsService
    from bollydog.entrypoint.websocket.app import SocketService
    hub_toml = pathlib.Path(__file__).parent / 'config.toml'
    with open(hub_toml, 'rb') as f:
        merged = tomllib.load(f)
    if config:
        work_dir = pathlib.Path(config).parent
        sys.path.insert(0, work_dir.as_posix())
        with open(config, 'rb') as f:
            merged.update(tomllib.load(f))
    for node_name, node_conf in merged.items():
        module = node_conf.pop('module', node_name)
        smart_import(module).create_from(**node_conf)
    if os.getenv('ENTRYPOINT_HTTP_ENABLED', '0') == '1': HttpService.create_from()
    if os.getenv('ENTRYPOINT_WS_ENABLED', '0') == '1': SocketService.create_from()
    if os.getenv('ENTRYPOINT_UDS_ENABLED', '0') == '1': UdsService.create_from()
    for svc in list(AppService._apps.values()):
        if not isinstance(svc.depends, dict) or not svc.depends: continue
        resolved = {}
        for dep_key, dep_val in svc.depends.items():
            if dep_val is not None: resolved[dep_key] = dep_val; continue
            dep = AppService._apps.get(dep_key)
            if dep is None: raise ValueError(f"depends '{dep_key}' not found for {svc.domain}.{svc.alias}")
            svc.add_dependency(dep)
            resolved[dep_key] = dep
        svc.depends = resolved
    for svc in AppService._apps.values():
        if type(svc).commands: type(svc)._load_commands(type(svc).commands)


__all__ = ['load_from_config']
