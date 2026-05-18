"""Deferred imports inside load_from_config to avoid circular import with models.base -> service.config."""


def load_from_config(config: str = None) -> None:
    import pathlib
    import sys
    import tomllib
    from mode.utils.imports import smart_import
    from bollydog.models.service import AppService
    from bollydog.entrypoint.http.app import HttpService
    from bollydog.entrypoint.uds.app import UdsService
    from bollydog.entrypoint.websocket.app import SocketService
    from bollydog.service.config import BOLLYDOG_HTTP_ENABLED, BOLLYDOG_UDS_ENABLED, BOLLYDOG_WS_ENABLED
    if config:
        work_dir = pathlib.Path(config).parent
        sys.path.insert(0, work_dir.as_posix())
        with open(config, 'rb') as f:
            for node_name, node_conf in tomllib.load(f).items():
                module = node_conf.pop('module', node_name)
                smart_import(module).create_from(**node_conf)
    if BOLLYDOG_HTTP_ENABLED: HttpService.create_from()
    if BOLLYDOG_WS_ENABLED: SocketService.create_from()
    if BOLLYDOG_UDS_ENABLED: UdsService.create_from()
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
