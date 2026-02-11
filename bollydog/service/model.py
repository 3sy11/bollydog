from bollydog.models.base import BaseBaseCommand

DOMAIN = 'bollydog'

class TaskList(BaseCommand):
    domain = DOMAIN

class TaskCount(BaseCommand):
    domain = DOMAIN

class TaskState(BaseCommand):
    domain = DOMAIN
