# Bollydog Development Workflow (SOP)

Standard development workflow for building systems with the bollydog framework. Starting from scenario narratives, through DDD domain partitioning, behavior design, service responsibility, end-to-end tracing, interface contracts, to TDD behavior verification and walking skeleton, forming a complete "story-driven → behavior-verified → build-up" loop.

Core methodology sources:
- **Event Storming / DDD**: Start from verbs (behaviors), not nouns (entities)
- **Cosmic Python**: Dependency inversion, Command/Event separation, Service Layer testing, Repository abstraction
- **Walking Skeleton (GOOS)**: Thinnest possible end-to-end slice
- **TDD High/Low Gear**: Domain model in low gear (precise feedback), Command layer in high gear (high coverage, low coupling)

## Overview

```
Phase 0  Scenario Narrative ──→ Accumulate scenario stories, extract core descriptions
Phase 1  Domain Boundary ─────→ Partition DDD bounded contexts from story subjects
Phase 2  Behavior Design ─────→ Inter-subject calls, events, and reactions
Phase 3  Service Responsibility → What each subject does internally
Phase 4  End-to-End Tracing ──→ Sequence diagrams with parameter semantics
Phase 5  Interface Contract ──→ All signatures + data models + serialization
Phase 6  Behavior Verification → Command as TDD unit, MemoryProtocol-driven
Phase 7  Walking Skeleton ────→ Build service skeleton on verified behaviors
Phase 8  Iterative Delivery ──→ Replace stubs layer by layer
```

### Deliverable Map

```
docs/
├── 00-scenarios.md       ← Phase 0-3: Scenarios + domain + behavior + service declarations
├── 01-sequence.md        ← Phase 4: End-to-end sequence diagrams
├── 02-interfaces.md      ← Phase 5: Interface signatures + data models + serialization
└── 04-skeleton.md        ← Phase 7: Skeleton notes + config + run commands
tests/
└── test_*.py             ← Phase 6: Behavior verification test cases
```

---

## Phase 0: Scenario Narrative

**Goal**: Accumulate enough usage scenarios to form the first document. No design decisions.

### What to Do

Describe system usage scenarios in plain natural language. One sentence per scenario:

```
[Who] did [what action], the system [did what], and ultimately [produced what result].
```

### Rules

- **Zero class names**: No technical terms (AppService, Command, Protocol) in scenarios
- **Zero technical details**: No mention of databases, APIs, message queues
- **Enough coverage**: At least 3-5 core scenarios + 2-3 exception scenarios
- Read it to a non-technical person — they should understand what happens

### Checkpoints

- Each scenario's core description fits in one sentence
- Scenario set covers the system's main value proposition
- Exception scenarios are covered (what happens on failure)

---

## Phase 1: Domain Boundary

**Goal**: Identify subjects from scenario stories and partition DDD bounded contexts.

### What to Do

1. Extract all **verbs** (behaviors, actions) from Phase 0 scenarios
2. Group behaviors by **responsibility** — each group is a bounded context
3. Name each context as a `domain`, identify subjects within (future AppServices)

### Mapping

| Story Element | Bollydog Mapping |
|--------------|-----------------|
| Story subject | AppService |
| Subject's responsibility scope | domain |
| Inter-subject interaction | Command / Event (Phase 2) |

### Rules

- Each subject's responsibility fits in one sentence
- Subjects in different domains **never directly call** each other's methods
- If a subject's responsibility exceeds one sentence, consider splitting

### Deliverable

Domain partition table:

| domain | Subject | One-sentence Responsibility | Story Source |
|--------|---------|---------------------------|-------------|

### Checkpoints

- Every action in scenario stories is assigned to a subject
- No orphaned subjects (no "nobody owns this" behavior)
- Subject boundaries are clear (no overlap)

---

## Phase 2: Behavior Design

**Goal**: Describe inter-subject interaction — who calls whom, who emits events, who reacts to what.

### What to Do

Return to scenario stories. For each subject, ask:

1. **What does it actively do?** → Command (imperative naming)
2. **Who does it notify on completion?** → Event (past-tense naming)
3. **What does it react to?** → Subscriber (`{topic: method_name}`)

### Command vs Event (from Cosmic Python Ch.10)

| | Command | Event |
|--|---------|-------|
| Mood | Imperative ("do this") | Past tense ("this happened") |
| Target | Specific receiver | All listeners |
| Failure | Fail noisily | Fail independently |
| bollydog | `BaseCommand` + `hub.dispatch` | `BaseEvent` + Exchange broadcast |

### Deliverable

**Behavior mapping table** (one per subject):

| Subject | Commands Emitted | Events Emitted | Subscribed Topic → Reaction Method |
|---------|-----------------|----------------|-----------------------------------|

### destination Naming Convention

Three-segment: `domain.ServiceAlias.CommandAlias`

### Checkpoints

- Every interaction in scenarios maps to the behavior table
- Every Command has a clear receiver
- Every Event's emission timing is clear (after Command success)
- Cross-domain interaction only via Command/Event, no direct calls

---

> **Phase 0-3 deliverables are consolidated into `docs/00-scenarios.md`**

---

## Phase 3: Service Responsibility

**Goal**: Define what each subject does internally — its capabilities and resources.

### What to Do

For each subject from Phase 1:

1. **What state/data does it hold?** → Determines Protocol type and composition
2. **What business methods does it expose?** → Methods that Commands will call
3. **What does it depend on?** → `depends` list (lifecycle ordering)
4. **What does startup/shutdown require?** → Lifecycle hooks

### Protocol Composition Design

Protocol is not just "pick one from a list." Based on data characteristics from story narratives, Protocols may need to be **composed, nested, and layered** to meet actual requirements.

**Base Protocol types**:

| Port Abstraction | Applicable Pattern | Available Implementations |
|-----------------|-------------------|--------------------------|
| `KVProtocol` | Key-value storage | `MemoryProtocol`, `RedisProtocol`, `SQLiteProtocol` |
| `CRUDProtocol` | Relational CRUD | `PostgreSQLProtocol`, `DuckDBProtocol`, `SqlAlchemyProtocol` |
| `GraphProtocol` | Graph traversal | `Neo4jProtocol` |
| `FileProtocol` | File read/write | `TOMLFileProtocol` |

**Composite Protocol** (nested composition):

A subject may need multiple data capabilities simultaneously. bollydog Protocols support chained nesting, outer wrapping inner:

```
CacheLayer(inner=SQLiteProtocol)      hot cache + cold storage
TableCacheLayer(inner=DuckDBProtocol)  table-level cache + columnar storage
```

**Protocol design decision flow**:

1. Identify data **read/write patterns** from story narratives (frequent reads? batch writes? structured queries?)
2. Select **base Protocol** matching the read/write pattern
3. Determine if **composite capabilities** are needed (cache layer, transaction guarantees, multi-source aggregation)
4. Verify the composed Protocol can still be replaced with `MemoryProtocol` for testing

Final selection must satisfy: **production uses real implementation, tests use `MemoryProtocol`, zero code changes**. This is the core of bollydog's dependency inversion principle.

### Lifecycle Hooks (mode.Service)

```
on_init_dependencies → Create child services
on_first_start       → One-time initialization
on_start             → Every startup (load commands, init adapters)
on_started           → Ready (all dependencies started)
on_stop              → Shutdown (cleanup resources)
```

### Design Principles

- **AppService = Resource holder**. Expose business methods for Commands to call, never dispatch proactively
- **Command = Thin orchestration layer**. Call `app.method()` + `protocol.set()`, hold no state
- **Protocol = Environment abstraction**. Swap implementation without changing code

### Deliverable

Service declaration for each subject (structure only, no implementation).

---

## Phase 4: End-to-End Tracing

**Goal**: Draw sequence diagrams for key paths, specifying parameters and return values at each step.

**This step validates Phase 0-3 completeness** — missing data, overlooked interfaces, broken chains all surface here.

### Format

Expand step by step using bollydog dispatch semantics:

```
User trigger
  → Hub.dispatch(PushBars(symbol: str, interval: str, bars: list[dict], replay: bool))
    → PushBars.__call__() → dict
      → app.append_bars(symbol, interval, bars) → None
      → protocol.set(key, data)
      → yield SubCommand(field1: type, ...) → result
    → _publish(destination) → Exchange.match(topic)
      → SubscriberMethod(message) → ...
  ← User sees result
```

**Command signature convention**: A Command's input parameters are its own field definitions (excluding `_ModelMixin` / `BaseCommand` base fields). Use `CommandName(field1: type, field2: type, ...) → ReturnType` format throughout all sequence diagrams and method call tables. Never write `__call__()` with empty parentheses — always expand the Command's fields as parameters.

### Rules

- Every arrow must specify: **method name + parameter types + return type**
- Command arrows use the Command signature format: `CommandName(fields...) → ReturnType`
- All Command fields and return values must be primitive types (`str`, `int`, `float`, `bool`, `list`, `dict`, `None`)
- Trace from user input to user-visible output, no skipping
- Cross-domain communication only via `hub.dispatch` or Exchange
- Descriptive text doesn't count ("then it processes" ← must be expanded)

### Typical Issues Exposed

| Issue | Meaning |
|-------|---------|
| A Command needs data but nobody passes it | Interface gap |
| A call segment has no clear implementation | Design blind spot |
| Data needs persistence but no Protocol exists | Storage gap |
| Two subjects call each other's methods | Boundary violation |

### Deliverable

`docs/01-sequence.md` — one sequence diagram per core scenario.

---

## Phase 5: Interface Contract & Data Modeling

**Goal**: Extract all method signatures and data structures from Phase 4 sequence diagrams. Signatures produced here must correspond one-to-one with scenario stories and behavior design — no fabrication.

### 5a. Interface Signatures

For each subject in sequence diagrams, list all method signatures:

**Command signatures** — fields are the input parameters, `__call__` return type is the output. Both must be primitive types only (`str`, `int`, `float`, `bool`, `list`, `dict`, `None`):
```python
class DoSomething(BaseCommand):
    target: str
    value: float
    options: dict = {}
    async def __call__(self) -> dict | None: ...
```

Documented as: `DoSomething(target: str, value: float, options: dict) → dict | None`

Never return domain model classes or complex references from `__call__`. If a domain model is needed downstream, convert it to `dict` (e.g. `model.model_dump()`) before returning.

**Service method signatures**:
```python
class SomeService(AppService):
    async def process(self, data: InputModel) -> OutputModel: ...
    def get_state(self, key: str) -> dict: ...
```

**Subscriber signatures**:
```python
class AnotherService(AppService):
    subscriber = {'domain.SomeService.TaskDone': 'on_task_done'}
    async def on_task_done(self, message: BaseCommand) -> dict | None: ...
```

### 5b. Data Modeling

Derive data structures from signature parameters and return values. Every field must have usage evidence in sequence diagrams:

```python
class ResultModel(BaseDomain):
    id: str
    status: str
    value: float
    timestamp: float
```

No "maybe we'll need it later" fields.

### 5c. Serialization Scheme

Determine serialization for each data model:

| Data Model | Storage Location | Serialization | Read/Write Timing |
|-----------|-----------------|---------------|-------------------|

### Checkpoints

- Every arrow in Phase 4 sequence diagrams has a corresponding signature
- Every signature's parameters and return values have corresponding data models
- Every data model field is used in sequence diagrams
- Serialization scheme covers all models requiring persistence

### Deliverable

`docs/02-interfaces.md` — interface signatures + data models + serialization mapping

---

## Phase 6: Behavior Verification (TDD)

**Goal**: Before building any skeleton, verify all behaviors meet expectations through tests.

### Core Concept

bollydog's Command pattern is inherently TDD-friendly:

1. **Command is a Pydantic model** — all primitive types, naturally serializable, constructable, assertable
2. **Protocol is a dependency-inverted abstraction** — swap in `MemoryProtocol` for testing, zero external dependencies
3. **Command's `__call__` is pure orchestration** — deterministic input → deterministic output

This means: **no Hub, no service startup, no config file** needed to verify each Command's behavior.

### TDD High/Low Gear (from Cosmic Python Ch.5)

| Gear | Test Level | Purpose | bollydog Mapping |
|------|-----------|---------|-----------------|
| **Low** | Domain model | Precise feedback, design exploration | Test `BaseDomain` methods directly |
| **High** | Service Layer | High coverage, low coupling | Test `Command.__call__` |

**Use high gear most of the time** (test Commands); drop to low gear only for complex business logic (test domain model methods).

### Test Build Order

```
1. Domain model unit tests (low gear)
   → Test BaseDomain methods
   → No Protocol, no Hub, pure in-memory computation

2. Command behavior tests (high gear)
   → Construct MemoryProtocol, pre-populate data
   → Instantiate Command, directly await cmd()
   → Assert return value + side effects in Protocol

3. Cross-service interaction tests
   → Use Hub + Exchange
   → Verify Event broadcast + Subscriber triggering
   → Mock app.method return values
```

### Test Template

```python
async def test_command_basic_flow():
    """Phase 0 scenario: [describe the corresponding scenario story]"""
    proto = MemoryProtocol()
    await proto.start()
    await proto.set('__initial_state', {'key': 'value'})

    cmd = SomeCommand(param='input')
    result = await cmd()

    assert result is not None
    state = await proto.get('__initial_state')
    assert state['key'] != 'value'  # verify side effects
```

### Use Primitive Types in Tests (from Cosmic Python Ch.5)

Service Layer tests should use primitive types (str, int, float) rather than domain objects. This decouples tests from the domain model:

```python
# Good: primitive types
cmd = SomeCommand(target='abc', value=1.0)

# Avoid: constructing domain objects in tests
obj = DomainObj(name='abc', ...); cmd = SomeCommand(obj=obj)
```

### Checkpoints

- Every Command from Phase 5 has a corresponding test
- Tests cover core paths and exception paths from scenario stories
- All tests run with `MemoryProtocol`, no external dependencies
- Behavior verification passes before entering Phase 7

### Deliverable

Test case files under `tests/` directory

---

## Phase 7: Walking Skeleton

**Goal**: Build a service skeleton on top of Phase 6 verified behaviors, making the system run end-to-end.

The skeleton **provides a runtime environment for verified Command behavior chains**. Phase 6 proves each Command works independently; Phase 7 proves they work together.

### Build Order (bottom-up)

```
1. Protocol instantiation
   → TOML-configure Protocol chain
   → Verify Protocol start/stop

2. Service declaration
   → AppService class definition, mount Protocol
   → commands / subscriber / depends declarations

3. Service registration and configuration
   → Write config.toml
   → load_from_config validation

4. Hub integration
   → Hub startup, dispatch main path
   → _publish + Exchange broadcast verification

5. Entry point verification
   → bollydog ls      ← confirm all Commands registered
   → bollydog execute ← end-to-end main path
```

### TOML Configuration Template

TOML should be **minimal** — only framework-level wiring keys and overrides of non-default service parameters. Service-level custom parameters are defined in `__init__` with defaults; TOML's role is override, not definition.

```toml
# Framework-level keys: commands, subscriber, depends, protocol — always explicit
["myapp.services.SomeService"]
commands = ["commands"]
depends = ["infra.ConfigSvc"]

["myapp.services.SomeService".subscriber]
"domain.*.TaskDone" = "on_task_done"

# Protocol parameters: only include values that differ from class defaults
["myapp.services.SomeService".protocol]
module = "bollydog.adapters.composite.CacheLayer"

["myapp.services.SomeService".protocol.protocol]
module = "bollydog.adapters.memory.SQLiteProtocol"
path = "data/state.db"
```

### Stub Strategy & `_stub_` Decremental Tracking

**Stub** is a placeholder implementation — complete function signature but returns hardcoded fake data, solely to make the call chain runnable. During skeleton phase, main paths use real implementations, non-main paths use stubs temporarily.

**Naming rule**: All stub methods use the `_stub_` prefix:

```python
class SomeCommand(BaseCommand):
    async def __call__(self):
        result = app.process(self.data)         # real implementation
        details = self._stub_enrich(result)     # stub: returns placeholder data
        return {'result': result, 'details': details}

    def _stub_enrich(self, data):
        return {'enriched': False, 'raw': data}
```

**Decremental tracking**: The `_stub_` prefix makes project completion quantitatively trackable:

```bash
grep -rn "_stub_" myapp/        # list all stubs
grep -rc "_stub_" myapp/        # count stubs per file
```

Each iteration replaces a batch of stubs with real implementations; `grep` results decrease each round. When `grep` finds no `_stub_`, all features are complete.

### System Execution

After skeleton implementation, verify the system with these commands:

```bash
# List all registered Commands
bollydog ls --config config.toml

# Execute a single Command end-to-end
bollydog execute SomeCommand --config config.toml --param value

# Start service (HTTP mode)
bollydog serve --config config.toml --http

# Start service (WebSocket mode)
bollydog serve --config config.toml --ws

# Start service (UDS mode)
bollydog serve --config config.toml --uds /tmp/myapp.sock
```

### End-to-End Tests

After skeleton runs, add a few E2E tests. Cosmic Python's guiding principle:

> **One E2E test per feature**. Goal is to verify all components are glued correctly, not to verify business logic (that's Phase 6's job).

```python
async def test_e2e_main_flow():
    """Verify main path: [corresponding Phase 0 core scenario]"""
    async with Hub() as hub:
        msg = SomeCommand(param='value')
        await hub.execute(msg)
        # assert final state
```

### Checkpoints

- `bollydog ls` shows all expected Commands
- `bollydog execute` runs main path end-to-end
- Phase 4 sequence diagram main paths are all traceable
- Stub count is known and finite

### Deliverable

`docs/04-skeleton.md` — containing:
- Skeleton implementation notes (what's real, what's stub)
- TOML configuration file content
- System startup and verification commands
- Stub inventory (`grep _stub_` results)

---

## Phase 8: Iterative Delivery

After skeleton runs, flesh out layer by layer. Each iteration does one thing.

### Iteration Workflow

**Each iteration starts from story narrative**, following the full Phase 0 → Phase 7 path, but most content should be reusable from existing design:

```
1. Select the story scenario (or sub-scenario) for this iteration
2. Check reuse list:
   □ Domain partition (Phase 1) covered? → Reuse
   □ Behavior mapping (Phase 2) covered? → Reuse
   □ Service declaration (Phase 3) covered? → Reuse
   □ Sequence diagram (Phase 4) covered? → Reuse
   □ Interface signature (Phase 5) covered? → Reuse
3. If a Phase cannot be reused, new design content is needed
   → Explicitly list what needs to be added
   → Supplement the corresponding Phase document
4. Write behavior tests (Phase 6)
5. Replace corresponding stubs (Phase 7)
6. Verify end-to-end path
```

### Reuse Assessment Table

Fill in before each iteration:

| Phase | Reusable? | New Content Needed | Impact Scope |
|-------|----------|-------------------|--------------|
| 1 Domain Boundary | | | |
| 2 Behavior Design | | | |
| 3 Service Responsibility | | | |
| 4 Sequence Diagram | | | |
| 5 Interface Contract | | | |

If more than 2 Phases need new content, consider splitting into multiple iterations.

### Priority

1. **Core path**: System is unusable without it
2. **Enhancement path**: Improves quality
3. **Edge path**: Only needed in extreme cases

### Per-Iteration Checklist

```
□ This iteration's story: [one-sentence description]
□ Which arrow in Phase 4 sequence diagram?
□ Is the signature defined in Phase 5? If not, add it first
□ Need new data models? Add to Phase 5 first
□ Which stubs replaced? Confirm with grep _stub_
□ Phase 6 tests passing?
□ CLI still runs end-to-end?
```

### Stub Decremental Tracking

```bash
grep -r "_stub_" myapp/
```

All replaced = feature complete.

---

## Design Audit (Quality Gate)

Use this checklist at key milestones:

| Phase | Audit Point | Pass Criteria |
|-------|------------|---------------|
| 0 | Zero class names in stories | Non-technical person understands |
| 1 | Single responsibility per subject | Fits in one sentence |
| 2 | Command/Event clearly distinguished | Command imperative, Event past-tense |
| 3 | Protocol composition is sound | Tests can use MemoryProtocol |
| 4 | Sequence diagram arrows are precise | Method + params + return type |
| 5 | Signatures match stories | No fabricated interfaces |
| 6 | All behavior tests pass | Runnable without external deps |
| 7 | Skeleton runs end-to-end | CLI-verifiable |

---

## Test Pyramid

```
        ╱╲
       ╱  ╲         E2E tests (few)
      ╱    ╲        One per feature, verify glue
     ╱──────╲
    ╱        ╲       Command behavior tests (many)
   ╱          ╲      High-gear TDD, MemoryProtocol-driven
  ╱────────────╲
 ╱              ╲     Domain model unit tests (as needed)
╱                ╲    Low-gear TDD, complex business logic
╲────────────────╱
```

- **Bottom**: Domain model methods — precise feedback but coupled to implementation
- **Middle**: Command `__call__` — driven by primitive types, covers all business scenarios
- **Top**: E2E (Hub + real Protocol) — only verifies integration correctness

> "If you find yourself needing to manipulate domain objects directly to prepare data in Command tests, your Command layer isn't complete enough." — Cosmic Python Ch.5

---

## Quick Reference

| Phase | Deliverable | Question Answered | Cost of Skipping |
|-------|------------|-------------------|-----------------|
| 0 Scenario | Story set | What does the system do | Design deviates from requirements |
| 1 Domain | Partition table | Where are boundaries | Responsibility confusion |
| 2 Behavior | Mapping table | Who interacts with whom | Interfaces constantly reworked |
| 3 Service | Declarations | What each subject does | Wrong Protocol, tangled dependencies |
| 4 Tracing | Sequence diagrams | How behavior occurs | Structure without behavior |
| 5 Contract | Signatures + models | Precise agreements | Rework during implementation |
| 6 Verification | Test cases | Is behavior correct | Skeleton built, then logic errors found |
| 7 Skeleton | Runnable code | Does it run together | Integration issues discovered late |
| 8 Delivery | Complete impl | Is it feature-complete | Big-bang delivery risk |
