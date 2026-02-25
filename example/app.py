from bollydog.models.service import AppService
import example.commands  # noqa: trigger command registration


class ExampleService(AppService):
    domain = 'example'
    router_mapping = {
        'Ping': ['GET', '/api/ping'],
        'Echo': ['POST', '/api/echo'],
        'Countdown': ['SSE', '/api/countdown'],
    }
