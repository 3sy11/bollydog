"""Layer 1: Pure logic tests — no asyncio, no Service lifecycle."""
from bollydog.service.exchange import match_topic
from bollydog.models.base import BaseCommand, BaseEvent


# ─── match_topic ──────────────────────────────────────────────

def test_exact_match():
    assert match_topic("a.b.c", "a.b.c")

def test_exact_mismatch():
    assert not match_topic("a.b.c", "a.b.d")

def test_wildcard_single_segment():
    assert match_topic("a.*.c", "a.b.c")
    assert match_topic("a.*.c", "a.x.c")
    assert not match_topic("a.*.c", "a.b.d")

def test_wildcard_does_not_span():
    assert not match_topic("a.*", "a.b.c")

def test_hash_matches_zero_or_more():
    assert match_topic("a.#", "a")
    assert match_topic("a.#", "a.b")
    assert match_topic("a.#", "a.b.c.d")

def test_hash_in_middle():
    assert match_topic("a.#.z", "a.z")
    assert match_topic("a.#.z", "a.b.c.z")

def test_hash_only():
    assert match_topic("#", "a.b.c")

def test_mixed_wildcard_and_hash():
    assert match_topic("a.*.#", "a.b")
    assert match_topic("a.*.#", "a.b.c.d")
    assert not match_topic("a.*.#", "a")


# ─── BaseCommand.__init_subclass__ ───────────────────────────

def test_command_subclass_gets_alias_and_module():
    class Foo(BaseCommand):
        x: int = 0
        async def __call__(self):
            return self.x
    assert Foo.alias == 'Foo'
    assert Foo.module == __name__
    assert Foo.destination.endswith('.Foo')

def test_event_subclass():
    class SomethingHappened(BaseEvent):
        pass
    assert SomethingHappened.alias == 'SomethingHappened'

def test_command_derive_isolates_destination():
    class Bar(BaseCommand):
        async def __call__(self):
            return 1
    derived = Bar._derive('myapp.MySvc')
    assert derived.destination == 'myapp.MySvc.Bar'
    assert Bar.destination != derived.destination

def test_command_str():
    class Baz(BaseCommand):
        async def __call__(self):
            return 0
    inst = Baz()
    s = str(inst)
    assert 'Command(Baz)' in s
    assert 'trace=' in s
