import random
import pytest
from pydantic import Field
from bollydog.models.base import Command, BaseDomain
from bollydog.globals import protocol as _protocol, message as _message
from bollydog.service.handler import AppHandler
from bollydog.service.app import HubService


class Point(BaseDomain):
    x: int
    y: int


class LogPoint(Command):
    domain: str = Field(default='service')
    point: Point


class RandMovePoint(Command):
    point: Point
    domain: str = Field(default='service')
    x: int = Field(default_factory=lambda: random.randint(0, 1))
    y: int = Field(default_factory=lambda: random.randint(0, 1))


async def print_point(command: LogPoint = _message, protocol=_protocol):
    print(f"Point: {command.point.x}, {command.point.y}")


async def move_point(command: RandMovePoint = _message, protocol=_protocol):
    yield LogPoint(point=command.point)
    point = command.point
    point.x = point.x + command.x
    point.y = point.y + command.y
    yield LogPoint(point=point)


@pytest.mark.asyncio
async def test_async_generator_handler():
    hub = HubService.create_from(domain='test', apps=[])
    AppHandler.register(LogPoint, print_point, app=hub)
    AppHandler.register(RandMovePoint, move_point, app=hub)
    point = Point(x=0, y=0)
    log_point = LogPoint(point=point)
    tasks = hub.get_coro(log_point)
    for task in tasks:
        await task()
    tasks = hub.get_coro(RandMovePoint(point=point))
    for task in tasks:
        await task()
