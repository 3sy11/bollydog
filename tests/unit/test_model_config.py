from bollydog.models.config import ServiceConfig

from bollydog.patch import yaml


def test_load_config():
    _config = """
http_service:
    app: !module bollydog.entrypoint.http.app.HttpService
    middlewares:
        -   middleware: !module starlette.middleware.sessions.SessionMiddleware
            secret_key: ${BOLLYDOG_HTTP_SERVICE_SECRET_KEY}
        -   middleware: !module starlette.middleware.authentication.AuthenticationMiddleware
            backend: !module bollydog.entrypoint.http.middleware.base_auth_backend
        -   middleware:  !module bollydog.entrypoint.http.middleware.ASGIMiddleware
ws_service:
    app: !module bollydog.entrypoint.websocket.app.SocketService

    """
    config = yaml.safe_load(_config)
    # config = ServiceConfig.model_construct(**config['datasource'])
    config = ServiceConfig(**config['http_service'])
