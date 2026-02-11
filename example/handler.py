from bollydog.models.base import BaseCommand

DOMAIN = 'example'

class TaskList(BaseCommand):
    domain = DOMAIN

class TaskCount(BaseCommand):
    domain = DOMAIN
