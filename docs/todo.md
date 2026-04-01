# Bollydog design & enhancement backlog

## Pending (current phase)

- **Exchange publish Command**: expose a `BaseCommand` on Exchange/Hub for manual/ops event injection (complements `hub.emit`, enables unified entry + audit).
- **Async generator yield Command**: `_run_gen` supports `yield SomeCommand(...)` — Hub dispatches sub-task, sends result back to generator. Current `_run_gen` has basic yield-Command support; needs refinement for error propagation.
- **Async generator yield Event**: `_run_gen` supports `yield SomeEvent(...)` — Hub broadcasts via Exchange, fire-and-forget, generator continues without blocking. Needs branch in `_run_gen` to distinguish Command (await result) vs Event (fire-and-forget).

## L0 core (completed)

- ~~Hub pipeline: _fire + _publish + _run/_run_gen pure execution~~
- ~~_with_context lifted to call sites (_fire, _process_queued, execute)~~
- ~~Hub._publish: match topic via exchange.match(), instantiate handler Command~~
- ~~Exchange pure router: match(topic)->set, no handler instantiation~~
- ~~Hub._resolve_app destination fast-fail (DestinationNotFoundError)~~
- ~~hub.get_service(cls_or_key, required=True)~~
- ~~_run_gen/_iterate merged into single method~~
- ~~Hub dispatch three-tier: Event/Command qos0/Command qos1~~
- ~~BaseEvent duck-typing (removed qos override)~~
- ~~Callable subscription removed: subscribe only supports Command classes~~
- ~~BaseCommand.data + add_event/get_event~~
- ~~UDS entrypoint (`UdsService`, length-prefixed JSON, CLI execute socket forward / `--local`)~~

## L0 core (pending)

- destination routing semantics refinement (P1)
- `@timer` / `@cron` (P2)
- Service-level `@handle(CommandClass)` (P3)

## L2 orchestration

- Thread multi-turn session (P0)
- Middleware chain (P0)
- Parallel fan-out aggregation (P0)
- Handoff (P1)
- capabilities declaration (P1)

## L1 distributed

- Transport (P0)
- Registry (P0)
- RemoteDispatch (P0)
- Event Federation (P1)
- Envelope serialization (P0)
- Hub Identity (P0)
- Load balancing (P1)

## L3 agent

- Tool + MCP (P1)
- Layered Memory (P2)
- Declarative DAG (P3)

See `timing/ANALYSIS_BOLLYDOG_FIT.md` for details.
