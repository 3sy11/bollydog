import random
import pytest
from pydantic import Field
from bollydog.models.base import Command, BaseDomain
from bollydog.service.handler import AppHandler
from bollydog.service.app import HubService
from bollydog.exception import HandlerNoneError


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


@pytest.mark.asyncio
async def test_no_handler_raises():
    """减法后，没有注册入口，get_coro 应抛出 HandlerNoneError"""
    hub = HubService.create_from(domain='test', apps=[])
    point = Point(x=0, y=0)
    log_point = LogPoint(point=point)
    with pytest.raises(HandlerNoneError):
        hub.get_coro(log_point)
