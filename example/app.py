from bollydog.models.service import AppService

class ExampleService(AppService):

    def __init__(self, *args, **kwargs):
        super(ExampleService, self).__init__(*args, **kwargs)
