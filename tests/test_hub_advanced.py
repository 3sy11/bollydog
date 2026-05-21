"""Hub advanced tests — hooks, handoff, gather, async generator, subscriber.

All tests use the `hub` fixture (E2E via run_hub).
Commands are defined inline and registered dynamically.
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'example'))

from bollydog.models.base import BaseCommand, BaseEvent, BaseService
from bollydog.models.service import AppService


# ─── Hooks ────────────────────────────────────────────────────

async def test_before_hook_short_circuit(hub):
    """before hook returns non-None → short-circuit, Command never runs."""
    ran = []

    @hub.before
    async def guard(msg):
        if msg.alias == '_Blocked': return {'blocked': True}

    class _Blocked(BaseCommand):
        async def __call__(self):
            ran.append(1)
            return {'should': 'not reach'}

    derived = _Blocked._derive('bollydog.Hub')
    BaseService.registry[derived.destination] = derived
    result = await hub.execute(derived())
    assert result == {'blocked': True}
    assert ran == []


async def test_after_hook_receives_result(hub):
    """after hook receives result and exception."""
    captured = {}

    @hub.after
    async def audit(msg, result=None, exception=None):
        captured['result'] = result
        captured['exception'] = exception

    class _Audited(BaseCommand):
        async def __call__(self) -> dict:
            return {'ok': True}

    derived = _Audited._derive('bollydog.Hub')
    BaseService.registry[derived.destination] = derived
    await hub.execute(derived())
    assert captured['result'] == {'ok': True}
    assert captured['exception'] is None


# ─── Handoff ──────────────────────────────────────────────────

async def test_handoff_chain(hub):
    """Command returns another Command → handoff, result comes from target."""
    class _Step2(BaseCommand):
        async def __call__(self) -> dict:
            return {'from': 'step2', 'data': self.data}

    class _Step1(BaseCommand):
        async def __call__(self):
            return _Step2(data={'chain': True})

    for cls in (_Step1, _Step2):
        derived = cls._derive('bollydog.Hub')
        BaseService.registry[derived.destination] = derived

    result = await hub.execute(_Step1._derive('bollydog.Hub')())
    assert result['from'] == 'step2'
    assert result['data']['chain'] is True


# ─── Gather ───────────────────────────────────────────────────

async def test_gather_parallel(hub):
    """hub.gather dispatches multiple commands in parallel."""
    class _A(BaseCommand):
        async def __call__(self) -> int: return 1
    class _B(BaseCommand):
        async def __call__(self) -> int: return 2
    class _C(BaseCommand):
        async def __call__(self) -> int: return 3

    for cls in (_A, _B, _C):
        derived = cls._derive('bollydog.Hub')
        BaseService.registry[derived.destination] = derived

    results = await hub.gather([
        _A._derive('bollydog.Hub')(),
        _B._derive('bollydog.Hub')(),
        _C._derive('bollydog.Hub')(),
    ])
    assert sorted(results) == [1, 2, 3]


# ─── Async Generator (_run_gen) ───────────────────────────────

async def test_async_gen_pipeline(hub):
    """Async gen command: yield Command → get result as feedback, yield value → stream."""
    from example.commands import Ping

    class _GenPipe(BaseCommand):
        async def __call__(self):
            ping_result = yield Ping()
            yield {'pong': ping_result['pong'], 'tasks': ping_result['tasks']}

    derived = _GenPipe._derive('bollydog.Hub')
    BaseService.registry[derived.destination] = derived
    msg = derived()
    await hub.dispatch(msg)
    values = []
    async for v in msg.state:
        values.append(v)
    assert len(values) >= 1
    assert values[-1]['pong'] is True


async def test_async_gen_parallel_fan_out(hub):
    """yield [cmd, cmd, ...] → parallel fan-out, results as list feedback."""
    class _TaskX(BaseCommand):
        n: int = 0
        async def __call__(self) -> int: return self.n * 10

    derived_x = _TaskX._derive('bollydog.Hub')
    BaseService.registry[derived_x.destination] = derived_x

    class _FanOut(BaseCommand):
        async def __call__(self):
            results = yield [derived_x(n=1), derived_x(n=2), derived_x(n=3)]
            yield {'sums': sorted(results)}

    derived = _FanOut._derive('bollydog.Hub')
    BaseService.registry[derived.destination] = derived
    msg = derived()
    await hub.dispatch(msg)
    values = []
    async for v in msg.state:
        values.append(v)
    assert values[-1]['sums'] == [10, 20, 30]


# ─── Exchange subscriber ─────────────────────────────────────

async def test_event_triggers_subscriber(hub):
    """Emit Event → Exchange matches subscriber → subscriber command dispatched."""
    received = []

    class _TestService(AppService):
        domain = 'test'
        subscriber = {'test._TestService.ThingDone': 'on_done'}
        async def on_done(self, message):
            received.append(message.data)

    svc = _TestService()
    AppService._apps['test._TestService'] = svc
    await hub.exchange.on_started()

    class ThingDone(BaseEvent):
        destination = 'test._TestService.ThingDone'

    BaseService.registry['test._TestService.ThingDone'] = ThingDone
    evt = ThingDone(data={'info': 'ok'})
    await hub.execute(evt)
    await asyncio.sleep(0.15)
    assert len(received) >= 1


# ─── Hub _run retry/timeout path ──────────────────────────────

async def test_command_retry_on_timeout(hub):
    """Command with delivery_count > 0 retries on timeout."""
    attempts = []

    class _Slow(BaseCommand):
        expire_time: float = 0.05
        delivery_count: int = 1
        async def __call__(self) -> str:
            attempts.append(1)
            if len(attempts) == 1:
                await asyncio.sleep(1)  # trigger timeout on first try
            return 'ok'

    derived = _Slow._derive('bollydog.Hub')
    BaseService.registry[derived.destination] = derived
    result = await hub.execute(derived())
    assert result == 'ok'
    assert len(attempts) == 2

async def test_command_exception_sets_state(hub):
    """Command raising exception → state gets the exception."""
    class _Boom(BaseCommand):
        async def __call__(self):
            raise ValueError('kaboom')

    derived = _Boom._derive('bollydog.Hub')
    BaseService.registry[derived.destination] = derived
    import pytest
    with pytest.raises(ValueError, match='kaboom'):
        await hub.execute(derived())
