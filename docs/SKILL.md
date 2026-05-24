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
| [sop.md](sop.md) | 838 | 8-Phase workflow — what to do, in what order |
| [spec.md](spec.md) | 555 | Architecture, API, constraints — how things work |

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
| P6 Behavior Verification (TDD) | 338-445 | Writing tests, test pyramid |
| P7 Walking Skeleton | 446-586 | Building skeleton, TOML config, stubs |
| P8 Iterative Delivery | 587-783 | Issue protocol, registry, commit convention |
| Design Audit | 785-801 | Quality gate checklist |
| Test Pyramid | 802-825 | Layer 1-4 test structure |
| Quick Reference | 826-838 | Phase summary table |

### spec.md Index

| Section | Lines | Read When |
|---------|-------|-----------|
| Architecture Overview | 10-31 | Understanding system structure |
| Quick Start | 32-63 | First-time setup |
| Dispatch Pipeline | 64-78 | Hub dispatch flow |
| Command Patterns (4 types) | 79-149 | Designing commands |
| Globals (request-scoped) | 150-163 | Using hub/session context vars |
| Destination & Topic | 164-171 | Naming conventions |
| Exchange (pub/sub) | 172-203 | Subscriber/fan-out design |
| Hooks (before/after) | 204-217 | Middleware hooks |
| Session | 218-230 | Session management |
| AppService Design | 231-253 | Service class design |
| Protocol System | 254-341 | Base, ABC, implementations, composites |
| TOML Configuration | 342-420 | Config file structure, create_from |
| CLI | 421-430 | Command-line interface |
| Environment Variables | 431-482 | Env var naming, all variables |
| Design Rules | 483-492 | Hard constraints |
| Testing Strategy | 493-547 | Four-layer model, fixtures, utilities |
| Troubleshooting | 548-555 | Common issues |

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
7. Layer 1-3 tests: no Hub; Layer 4: `run_hub` fixture

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
