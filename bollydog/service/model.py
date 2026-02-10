from bollydog.models.base import Command

DOMAIN = 'bollydog'

class TaskList(Command):
    domain = DOMAIN

class TaskCount(Command):
    domain = DOMAIN

class TaskState(Command):
    domain = DOMAIN
