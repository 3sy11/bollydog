"""Deferred imports inside load_from_config to avoid circular import with models.base -> service.config."""
import os


def _cast_env(env_str: str, original):
    if isinstance(original, bool): return env_str.lower() in ('1', 'true', 'yes')
    if isinstance(original, int): return int(env_str)
    if isinstance(original, float): return float(env_str)
    return env_str


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
                smart_import(node_name).create_from(**node_conf)
    if BOLLYDOG_HTTP_ENABLED: HttpService.create_from()
    if BOLLYDOG_WS_ENABLED: SocketService.create_from()
    if BOLLYDOG_UDS_ENABLED: UdsService.create_from()
    for svc in AppService._apps.values():
        for key, val in svc.config.items():
            env = os.environ.get(key.upper())
            if env is None: continue
            svc.config[key] = _cast_env(env, val)
    for svc in list(AppService._apps.values()):
        resolved = []
        for dep_key in svc.depends:
            dep = AppService._apps.get(dep_key)
            if dep is None: raise ValueError(f"depends '{dep_key}' not found for {svc.domain}.{svc.alias}")
            svc.add_dependency(dep)
            resolved.append(dep)
        svc.depends = resolved
    seen = set()
    for svc in AppService._apps.values():
        if type(svc) in seen: continue
        seen.add(type(svc))
        if type(svc).commands: type(svc)._load_commands(type(svc).commands)


__all__ = ['load_from_config']
