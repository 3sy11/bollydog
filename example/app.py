from bollydog.models.service import AppService


class ExampleService(AppService):
    domain = 'example'
    commands = ['commands']
    routers = {
        'Ping': ['GET', '/api/ping'],
        'Echo': ['POST', '/api/echo'],
        'Countdown': ['SSE', '/api/countdown'],
    }
