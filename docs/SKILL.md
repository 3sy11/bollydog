# Bollydog Framework Development Skill

This skill guides AI in building systems with the bollydog framework. Two core documents: **spec.md** (normative — what the framework does and how) and **sop.md** (procedural — step-by-step development workflow). All operations must comply with spec.md constraints.

## Usage

1. **New system**: Follow `sop.md` Phase 0-8 sequentially; consult `spec.md` sections for framework details at each Phase
2. **Modify existing**: Identify current Phase, resume from there
3. **Troubleshoot**: See `spec.md` Troubleshooting section
4. **Audit design**: Use `sop.md` design audit checklist

## Document Relationship

| Document | Nature | Purpose |
|----------|--------|---------|
| `spec.md` | Normative | Architecture, API, configuration, constraints — "what and how" |
| `sop.md` | Procedural | Development workflow, Phase steps, deliverables — "in what order" |

**Principle**: Every step in `sop.md` must comply with `spec.md` constraints. When conflicts arise, `spec.md` takes precedence.

---

## spec.md Table of Contents

Normative document defining framework architecture, components, configuration, and constraints.

| Section | Content | SOP Link |
|---------|---------|----------|
| [Architecture Overview](#architecture-overview) | Hub/Command/Protocol three-layer architecture | Phase 1 Domain Boundary, Phase 3 Service Responsibility |
| [Quick Start](#quick-start) | Minimal runnable example | Phase 7 Walking Skeleton |
| [Dispatch Pipeline](#dispatch-pipeline) | dispatch → _fire → _run → _publish chain | Phase 4 End-to-End Tracing |
| [Command Patterns](#command-patterns) | Four Command patterns | Phase 2 Behavior Design, Phase 5 Interface Contract |
| — 1. Pure compute | No globals, pure computation | Phase 6 Low-gear TDD |
| — 2. Orchestration | app + protocol orchestration | Phase 6 High-gear TDD |
| — 3. Async generator | yield sub-commands, parallel fan-out | Phase 4 Sequence branching |
| — 4. Handoff | return delegation | Phase 4 Chain tracing |
| [Globals (request-scoped)](#globals-request-scoped) | hub/app/protocol/session/message proxies | Phase 3 Design Principles |
| [Destination & Topic](#destination--topic) | Three-segment naming and AMQP-style matching | Phase 2 destination naming |
| [Exchange (pub/sub)](#exchange-pubsub) | Event broadcasting and subscription | Phase 2 Behavior Design (Event/Subscriber) |
| [Hooks (before/after)](#hooks-beforeafter) | Before/after hooks | Phase 3 Lifecycle |
| [Session](#session) | Session state management | Phase 3 Service Responsibility |
| [AppService Design](#appservice-design) | Service design specification | Phase 3 full reference |
| [Protocol System](#protocol-system) | Protocol hierarchy and all implementations | Phase 3 Protocol Composition |
| — Base class | Protocol base class | |
| — ABC hierarchy | KV/CRUD/Graph/File four ports | Phase 3 Base Protocol types |
| — Implementations | All concrete implementations | Phase 3 Selection |
| — Mixins | Transaction/Dialect mixins | Phase 5 Serialization |
| — Composite Protocol | CacheLayer decorator pattern | Phase 3 Composite Protocol |
| — DialectMixin | SQL compilation | |
| [TOML Configuration](#toml-configuration) | Config file structure and loading | Phase 7 TOML config template |
| — Structure | Node structure | |
| — Service lifecycle | Loading lifecycle | Phase 3 Lifecycle hooks |
| [CLI](#cli) | Command-line tools | Phase 7 System execution |
| [Environment Variables](#environment-variables) | Env var overrides | Phase 7 Configuration |
| [Design Rules](#design-rules) | Framework design constraints | Design Audit |
| [Testing Strategy](#testing-strategy) | Testing strategy | Phase 6 full reference |
| [Troubleshooting](#troubleshooting) | Common issues | Diagnostics |

---

## sop.md Table of Contents

Procedural document defining development workflow steps, deliverables, and checkpoints.

| Section | Content | Deliverable |
|---------|---------|-------------|
| [Overview](#overview) | 8 Phase overview and deliverable map | — |
| [Phase 0: Scenario Narrative](#phase-0-scenario-narrative) | Natural language scenario collection | `00-scenarios.md` |
| [Phase 1: Domain Boundary](#phase-1-domain-boundary) | DDD bounded context partitioning | `00-scenarios.md` |
| [Phase 2: Behavior Design](#phase-2-behavior-design) | Inter-subject Command/Event/Subscriber mapping | `00-scenarios.md` |
| — Command vs Event | Cosmic Python Ch.10 distinction | |
| — destination naming | Three-segment naming convention | |
| [Phase 3: Service Responsibility](#phase-3-service-responsibility) | Intra-subject capabilities, Protocol, dependencies | `00-scenarios.md` |
| — Protocol Composition | Composite Protocol design decision flow | |
| — Lifecycle hooks | mode.Service five hooks | |
| — Design principles | AppService/Command/Protocol roles | |
| [Phase 4: End-to-End Tracing](#phase-4-end-to-end-tracing) | Sequence diagrams, expose design gaps | `01-sequence.md` |
| [Phase 5: Interface Contract & Data Modeling](#phase-5-interface-contract--data-modeling) | Signatures + data models + serialization | `02-interfaces.md` |
| — 5a. Interface signatures | Command / Service / Subscriber signatures | |
| — 5b. Data modeling | BaseDomain structure definitions | |
| — 5c. Serialization | Storage location + method + timing | |
| [Phase 6: Behavior Verification (TDD)](#phase-6-behavior-verification-tdd) | Command test-driven development | `tests/test_*.py` |
| — TDD high/low gear | Low=domain model, High=Command | |
| — Test build order | Unit → Behavior → Cross-service | |
| — Test template | MemoryProtocol-driven template | |
| [Phase 7: Walking Skeleton](#phase-7-walking-skeleton) | Bottom-up construction of runnable system | `04-skeleton.md` |
| — Stub strategy & `_stub_` tracking | Stub naming rules and progress tracking | |
| — System execution | CLI launch and verification commands | |
| [Phase 8: Iterative Delivery](#phase-8-iterative-delivery) | Story-driven iteration workflow | — |
| — Iteration workflow | Derive from story narrative, assess reuse | |
| — Reuse assessment table | Phase 1-5 reusability check | |
| [Design Audit](#design-audit) | Per-Phase audit checklist | |
| [Test Pyramid](#test-pyramid) | Three-layer testing strategy | |
| [Quick Reference](#quick-reference) | Per-Phase deliverable/question/cost summary | |

---

## SOP Execution Guide

### New System Development

```
Phase 0 → Write scenario stories (min 5 core + 3 exception)
Phase 1 → Extract subjects and domains     ← see spec.md "AppService Design"
Phase 2 → Design Command/Event/Subscriber  ← see spec.md "Command Patterns" + "Exchange"
Phase 3 → Define service responsibility    ← see spec.md "Protocol System"
Phase 4 → Draw sequence diagrams           ← see spec.md "Dispatch Pipeline"
Phase 5 → Export signatures and models     ← see spec.md "Globals" + "Destination & Topic"
Phase 6 → Write tests                      ← see spec.md "Testing Strategy"
Phase 7 → Build skeleton                   ← see spec.md "TOML Configuration" + "CLI"
Phase 8 → Iteratively replace stubs
```

### Key Constraints per Phase

| Phase | Required spec.md Compliance |
|-------|---------------------------|
| 2 | Command imperative naming, Event past-tense naming (Design Rules) |
| 2 | destination three-segment `domain.ServiceAlias.CommandAlias` (Destination & Topic) |
| 3 | Protocol must be replaceable with MemoryProtocol for testing (Protocol System) |
| 3 | AppService must not dispatch proactively (Design Rules) |
| 4 | Command signature = own fields as params + `__call__` return type. Never write `__call__()` with empty parens (End-to-End Tracing) |
| 5 | Command fields and return values must be primitive types only: `str`, `int`, `float`, `bool`, `list`, `dict`, `None` (Command Patterns / Design Rules) |
| 6 | Behavior tests must not depend on Hub (Testing Strategy) |
| 7 | `module` is a framework-reserved key in TOML (TOML Configuration) |

### Deliverable-to-Phase Mapping

```
docs/00-scenarios.md   ← P0 Scenarios + P1 Domain + P2 Behavior + P3 Service
docs/01-sequence.md    ← P4 End-to-end sequence diagrams
docs/02-interfaces.md  ← P5 Interface signatures + data models + serialization
tests/test_*.py        ← P6 Behavior verification test cases
docs/04-skeleton.md    ← P7 Skeleton notes + TOML config + run commands + stub list
```
