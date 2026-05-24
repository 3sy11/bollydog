---
name: bollydog-framework
description: >-
  Design and build async microservice systems using the bollydog framework.
  Guides through an 8-Phase workflow from scenario narratives, DDD domain
  partitioning, Command/Event design, Protocol selection, TDD verification,
  to walking skeleton. Use when creating a new bollydog project, adding
  features, or auditing an existing system design.
---

# Bollydog Framework

Async microservice framework built on `mode`. Commands as executable units, Hub as central dispatcher, Protocols as pluggable data layers.

## Instructions

Two documents drive development:

| Document | Role | Read When |
|----------|------|-----------|
| [sop.md](sop.md) | 8-Phase development workflow | What to do next |
| [spec.md](spec.md) | Architecture, API, constraints | Framework details at each Phase |

**Rule**: Every SOP step must comply with spec.md. Conflicts → spec.md wins.

### All Development is Issue-Driven

Every build — including the initial one — is an issue. Create a dated directory under `docs/issues/`, write the complete story-driven SOP docs (P0-P7) inside it, and merge results into `docs/REGISTRY.md` after tests pass.

| Phase | Do | spec.md Section |
|-------|----|-----------------|
| 0 | Write scenario stories | — |
| 1 | Extract domains | Architecture Overview |
| 2 | Design Command/Event/Subscriber | Command Patterns, Exchange, Destination & Topic |
| 3 | Define service internals | AppService Design, Protocol System, Globals |
| 4 | Draw sequence diagrams | Dispatch Pipeline |
| 5 | Define signatures and models | Command fields, Design Rules |
| 6 | Write tests (TDD) | Testing Strategy |
| 7 | Build skeleton | TOML Configuration, CLI, Environment Variables |
| 8 | Merge to REGISTRY | — |

### Issue Workflow

```
1. Create docs/issues/YYYYMMDD-name/
2. Write stories + design (P0-P5) in issue directory
3. Read REGISTRY → intersection analysis (record in notes.md)
4. Write tests → must pass (new + regression)
5. Build/modify skeleton → must run
6. Merge into REGISTRY.md
```

## Hard Constraints

Non-negotiable. Violating any produces a broken system:

1. Command names are imperative verbs; Event names are past tense
2. `destination` is three-segment: `domain.ServiceAlias.CommandAlias`
3. Command `__call__` fields and return values: primitive types only (`str`, `int`, `float`, `bool`, `list`, `dict`, `None`)
4. AppService must not dispatch proactively — only Commands dispatch
5. Protocol must be replaceable with MemoryProtocol for testing
6. `module` is a framework-reserved key in TOML config
7. Layer 1-3 tests must not depend on Hub; Layer 4 uses `run_hub` fixture

## Deliverables

```
docs/
├── REGISTRY.md           ← Living system registry (all issues merged here)
└── issues/               ← All design work lives here
    └── YYYYMMDD-name/    ← e.g. 20260524-initial-design/
        ├── stories.md    ← P0-P3: scenarios + domain + behavior + service
        ├── sequence.md   ← P4: sequence diagrams
        ├── interfaces.md ← P5: signatures + data models + serialization
        └── notes.md      ← intersection analysis + skeleton notes + decisions
tests/
└── test_*.py             ← P6: four-layer tests
```

## Additional Resources

- For the complete development workflow, see [sop.md](sop.md)
- For framework architecture and API reference, see [spec.md](spec.md)
- For design issue tracking, see [issue.md](issue.md)
