from pydantic import Field

from models.base import Command, Event


class TaskList(Command):
    pass


class TaskCount(Command):
    pass


class TaskDoneE(Event):
    pass


class ContinueMessage(Command):
    message: str = Field(init=True)
