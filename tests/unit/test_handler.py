import random
import pytest
from typing import AsyncGenerator, AsyncIterator, AsyncIterable
from pydantic import Field
from bollydog.models.base import Command, BaseDomain
from bollydog.globals import protocol as _protocol, message as _message
from bollydog.service.message import MessageManager


class Point(BaseDomain):
    x: int
    y: int


class LogPoint(Command):
    point: Point


class RandMovePoint(Command):
    point: Point
    x: int = Field(default_factory=lambda: random.randint(0, 1))
    y: int = Field(default_factory=lambda: random.randint(0, 1))


async def print_point(command: LogPoint = _message, protocol=_protocol):
    print(f"Point: {command.point.x},{command.point.y}")


async def move_point(command: RandMovePoint = _message, protocol=_protocol):
    yield LogPoint(point=command.point)
    point = command.point
    point.x = point.x + command.x
    point.y = point.y + command.y
    yield LogPoint(point=point)


MessageManager.register_handler(LogPoint, print_point)
MessageManager.register_handler(RandMovePoint, move_point)


@pytest.mark.asyncio
async def test_async_generator_handler():
    point = Point(x=0, y=0)
    log_point = LogPoint(point=point)
    tasks = MessageManager.create_tasks(log_point)
    for task in tasks:
        await task
    tasks = MessageManager.create_tasks(RandMovePoint(point=point))
    for task in tasks:
        await task
