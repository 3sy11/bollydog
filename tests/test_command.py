"""Layer 3: Command unit tests — with context, without Hub."""
from bollydog.testing import run_command
from bollydog.models.base import BaseCommand


class Add(BaseCommand):
    a: int = 0
    b: int = 0
    async def __call__(self) -> int:
        return self.a + self.b


class Greet(BaseCommand):
    name: str = 'world'
    async def __call__(self) -> dict:
        return {'greeting': f'hello {self.name}'}


async def test_pure_command():
    result = await run_command(Add(a=3, b=4))
    assert result == 7

async def test_command_with_defaults():
    result = await run_command(Add())
    assert result == 0

async def test_greet_command():
    result = await run_command(Greet(name='bollydog'))
    assert result == {'greeting': 'hello bollydog'}

async def test_command_with_protocol():
    from bollydog.adapters.memory import MemoryProtocol
    from bollydog.globals import protocol
    proto = MemoryProtocol()
    async with proto:
        class Store(BaseCommand):
            key: str = 'k'
            value: str = 'v'
            async def __call__(self) -> bool:
                await protocol.set(self.key, self.value)
                return True
        result = await run_command(Store(key='x', value='123'), protocol=proto)
        assert result is True
        assert await proto.get('x') == '123'
