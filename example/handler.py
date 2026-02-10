from bollydog.models.base import Command

DOMAIN = 'example'

class TaskList(Command):
    domain = DOMAIN

class TaskCount(Command):
    domain = DOMAIN
