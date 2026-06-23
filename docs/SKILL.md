---
name: bollydog-framework
description: >-
  Design and build async microservice systems using the bollydog framework.
  Use when creating a new bollydog project, adding features, or auditing
  an existing system design.
---

# Bollydog Framework

Async microservice framework built on `mode`. Commands as executable units, Hub as central dispatcher, Protocols as pluggable data layers.

## How to Use This Skill

Two reference documents drive development. **Do NOT read them in full** — use the indexes below and read by line range (`offset`/`limit`).

| Document | Lines | Role |
|----------|-------|------|
| [sop.md](sop.md) | 857 | 8-Phase workflow — what to do, in what order |
| [spec.md](spec.md) | 628 | Architecture, API, constraints — how things work |

**Rule**: Every SOP step must comply with spec.md. Conflicts -> spec.md wins.

### sop.md Index

| Section | Lines | Read When |
|---------|-------|-----------|
| Overview + Deliverable Map | 11-43 | Starting a project, understanding the flow |
| P0 Scenario Narrative | 44-70 | Writing user stories |
| P1 Domain Boundary | 71-109 | Partitioning bounded contexts |
| P2 Behavior Design | 110-154 | Designing Command/Event/Subscriber |
| P3 Service Responsibility | 155-220 | Protocol composition, lifecycle hooks |
| P4 End-to-End Tracing | 221-268 | Drawing sequence diagrams |
| P5 Interface Contract | 269-337 | Signatures, data models, serialization |
| P6 Behavior Verification (TDD) | 338-451 | Writing tests, test pyramid |
| P7 Walking Skeleton | 452-605 | Building skeleton, TOML config, stubs, run_execute |
| P8 Iterative Delivery | 606-803 | Issue protocol, registry, commit convention |
| Design Audit | 804-820 | Quality gate checklist |
| Test Pyramid | 821-844 | Layer 1-4 test structure |
| Quick Reference | 845-857 | Phase summary table |

### spec.md Index

| Section | Lines | Read When |
|---------|-------|-----------|
| Architecture Overview | 10-38 | Understanding system structure (Bootstrap, Registry, Hub) |
| Quick Start | 39-70 | First-time setup |
| Dispatch Pipeline | 71-106 | Two modes, CommandRunnerMixin, Hub vs ExecuteService |
| Command Patterns (4 types) | 107-177 | Designing commands |
| Globals (request-scoped) | 178-197 | Using hub/session/registry/services context vars |
| Destination & Topic | 198-205 | Naming conventions, dynamic subclass binding |
| Exchange (pub/sub) | 206-244 | Subscriber/fan-out design, RegistryService + Exchange |
| Hooks (before/after) | 245-258 | Middleware hooks |
| Session | 259-273 | Session management (get/set/delete/history) |
| AppService Design | 274-298 | Service class design, services registry |
| Protocol System | 299-386 | Base, ABC, implementations, composites |
| TOML Configuration | 387-479 | Config file structure, Bootstrap lifecycle |
| CLI | 480-498 | Command-line interface, fuzzy resolve, service vs execute |
| Environment Variables | 499-550 | Env var naming, all variables |
| Design Rules | 551-560 | Hard constraints |
| Testing Strategy | 561-619 | Four-layer model, fixtures, run_hub/run_execute |
| Troubleshooting | 620-628 | Common issues |

## Workflow Summary

All development — including the initial build — is issue-driven.

```
1. Create docs/issues/YYYYMMDD-name/
2. Write stories + design (P0-P5) in issue directory
3. Read REGISTRY -> intersection analysis
4. Maintain Registry Delta in notes.md
5. Write tests (P6) + build skeleton (P7)
6. Update REGISTRY.md, commit with delta trailers
```

### Commit Convention

Merge commits use **Conventional Commits** header + **Git Trailers**. REGISTRY.md is a pure current-state snapshot; traceability lives in git history only.

```
<type>(<scope>): <summary>

Issue: YYYYMMDD-name
Delta: + service FooService domain=x protocol=BarProtocol
Delta: ~ command DoThing dest=x.Foo.DoThing
```

- `+` add / `~` modify / `-` remove
- Entity types: `service` / `command` / `event` / `protocol` / `depends` / `config`
- Only on merge commit; search via `git log --grep="Delta.*EntityName"`

## Hard Constraints

1. Command names: imperative verbs; Event names: past tense
2. `destination`: three-segment `domain.ServiceAlias.CommandAlias`
3. Command `__call__` params/return: primitive types only
4. AppService must not dispatch — only Commands dispatch
5. Protocol must be replaceable with MemoryProtocol for testing
6. `module` is a framework-reserved TOML key
7. Layer 1-3 tests: no Hub; Layer 4: `run_hub` or `run_execute` fixture
8. CLI command is `service` (not `serve`); entrypoints toggled by env vars

## Deliverables

```
docs/
├── REGISTRY.md           <- Pure current-state snapshot (no history columns)
└── issues/
    └── YYYYMMDD-name/
        ├── stories.md    <- P0-P3
        ├── sequence.md   <- P4
        ├── interfaces.md <- P5
        └── notes.md      <- intersection + decisions + registry delta
tests/
└── test_*.py             <- P6: four-layer tests
```

## Additional Resources

- [sop.md](sop.md) — complete development workflow
- [spec.md](spec.md) — framework architecture and API
- [issue.md](issue.md) — design issue tracking
