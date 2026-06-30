"""Hub advanced tests — hooks, handoff, gather, async generator, subscriber.

All tests use the `hub` fixture (E2E via run_hub).
Commands are defined inline and registered dynamically via registry.commands.
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'example'))

from bollydog.globals import services, registry
from bollydog.models.base import BaseCommand, BaseEvent
from bollydog.models.service import AppService

DEST_PREFIX = 'bollydog.HubService'


def _reg(cmd_cls):
    """Register a command class into registry.commands via dynamic subclass."""
    destination = f'{DEST_PREFIX}.{cmd_cls.alias}'
    bound = type(cmd_cls.__name__, (cmd_cls,), {'destination': destination})
    registry.commands[destination] = bound
    return destination


def _make(cmd_cls, **kwargs):
    """Create instance via dynamic-subclass bound class."""
    destination = f'{DEST_PREFIX}.{cmd_cls.alias}'
    bound = type(cmd_cls.__name__, (cmd_cls,), {'destination': destination})
    registry.commands[destination] = bound
    return bound(**kwargs)


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

    result = await hub.execute(_make(_Blocked))
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

    await hub.execute(_make(_Audited))
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

    _reg(_Step2)
    result = await hub.execute(_make(_Step1))
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

    results = await hub.gather([_make(_A), _make(_B), _make(_C)])
    assert sorted(results) == [1, 2, 3]


# ─── Async Generator (_run_gen) ───────────────────────────────

async def test_async_gen_pipeline(hub):
    """Async gen command: yield Command → get result as feedback, yield value → stream."""
    from example.commands import Ping

    class _GenPipe(BaseCommand):
        async def __call__(self):
            ping_result = yield Ping()
            yield {'pong': ping_result['pong'], 'tasks': ping_result['tasks']}

    msg = _make(_GenPipe)
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

    _reg(_TaskX)

    class _FanOut(BaseCommand):
        async def __call__(self):
            results = yield [_TaskX(n=1), _TaskX(n=2), _TaskX(n=3)]
            yield {'sums': sorted(results)}

    msg = _make(_FanOut)
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
        async def on_done(self, message):
            received.append(message.data)

    svc = _TestService(subscriber={'test._TestService.ThingDone': 'on_done'})
    services['test._TestService'] = svc
    registry._register_subscribers('test._TestService', svc)

    class ThingDone(BaseEvent):
        destination = 'test._TestService.ThingDone'

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
                await asyncio.sleep(1)
            return 'ok'

    result = await hub.execute(_make(_Slow))
    assert result == 'ok'
    assert len(attempts) == 2

async def test_command_exception_sets_state(hub):
    """Command raising exception → state gets the exception."""
    class _Boom(BaseCommand):
        async def __call__(self):
            raise ValueError('kaboom')

    import pytest
    with pytest.raises(ValueError, match='kaboom'):
        await hub.execute(_make(_Boom))
