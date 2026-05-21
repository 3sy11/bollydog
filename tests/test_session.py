"""Session service tests — all methods via MemoryProtocol."""
from bollydog.adapters.memory import MemoryProtocol
from bollydog.service.session import Session


async def test_session_get_set():
    proto = MemoryProtocol()
    svc = Session()
    svc.protocol = proto
    async with proto:
        await svc.set('u1', {'name': 'alice'})
        assert await svc.get('u1') == {'name': 'alice'}

async def test_session_get_missing_returns_empty_dict():
    proto = MemoryProtocol()
    svc = Session()
    svc.protocol = proto
    async with proto:
        assert await svc.get('nonexist') == {}

async def test_session_delete():
    proto = MemoryProtocol()
    svc = Session()
    svc.protocol = proto
    async with proto:
        await svc.set('u1', {'x': 1})
        await svc.delete('u1')
        assert await svc.get('u1') == {}

async def test_session_append():
    proto = MemoryProtocol()
    svc = Session()
    svc.protocol = proto
    async with proto:
        await svc.append('u1', 'turns', {'role': 'user', 'msg': 'hi'})
        await svc.append('u1', 'turns', {'role': 'bot', 'msg': 'hello'})
        data = await svc.get('u1')
        assert len(data['turns']) == 2
        assert data['turns'][0]['msg'] == 'hi'

async def test_session_history():
    proto = MemoryProtocol()
    svc = Session()
    svc.protocol = proto
    async with proto:
        for i in range(5):
            await svc.append('u1', 'turns', {'i': i})
        assert len(await svc.history('u1')) == 5
        assert len(await svc.history('u1', last_n=2)) == 2
        last2 = await svc.history('u1', last_n=2)
        assert last2[0]['i'] == 3
        assert last2[1]['i'] == 4

async def test_session_history_missing_field():
    proto = MemoryProtocol()
    svc = Session()
    svc.protocol = proto
    async with proto:
        await svc.set('u1', {'name': 'bob'})
        assert await svc.history('u1', field='nofield') == []
