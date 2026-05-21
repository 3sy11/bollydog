"""StreamState tests — async generator Command streaming."""
import asyncio
from bollydog.models.state import StreamState


async def test_stream_put_and_iter():
    state = StreamState()
    await state.put({'count': 3})
    await state.put({'count': 2})
    await state.put(None)  # signals done
    values = []
    async for v in state:
        values.append(v)
    assert values == [{'count': 3}, {'count': 2}]

async def test_stream_done_after_none():
    state = StreamState()
    assert not state.done()
    await state.put(None)
    assert state.done()

async def test_stream_set_result():
    state = StreamState()
    state.set_result({'final': True})
    assert state.done()
    assert state.result() == {'final': True}

async def test_stream_set_exception():
    state = StreamState()
    state.set_exception(ValueError('boom'))
    assert state.done()
    assert isinstance(state.exception(), ValueError)

async def test_stream_await():
    state = StreamState()
    async def _produce():
        await asyncio.sleep(0.01)
        await state.put('v1')
        await state.put(None)
    asyncio.create_task(_produce())
    result = await state
    assert result == 'v1'

async def test_stream_multiple_results():
    state = StreamState()
    await state.put('a')
    await state.put('b')
    await state.put(None)
    assert state.result() == ['a', 'b']

async def test_stream_cancelled():
    state = StreamState()
    assert state.cancelled() is False

async def test_stream_state_property():
    state = StreamState()
    assert state._state == 'PENDING'
    await state.put(None)
    assert state._state == 'FINISHED'

async def test_stream_done_callback():
    state = StreamState()
    called = []
    state.add_done_callback(lambda s: called.append('cb'))
    await state.put(None)
    await asyncio.sleep(0.05)
    assert 'cb' in called

async def test_stream_done_callback_already_done():
    state = StreamState()
    await state.put(None)
    called = []
    state.add_done_callback(lambda s: called.append('late'))
    await asyncio.sleep(0.05)
    assert 'late' in called
