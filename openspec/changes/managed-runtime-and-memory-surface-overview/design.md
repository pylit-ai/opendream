## Context

Existing specs already provide:

- explicit local-first service lifecycle (`432`)
- observe health and live-check contracts (`442`)
- truthful semantic readiness and pruning evidence (`443`)

What is still missing is a coherent primary-path runtime policy and a compact operator summary of dream effects and memory state. The implementation should reuse existing service manifests, runtime metadata, worker health, mutation audits, and observability indexing rather than inventing a parallel control plane.

## Decisions

### Decision: Managed background runtime is primary-path explicit, not hidden
OpenDream will not spawn a mystery daemon behind the operator's back. Instead, primary commands such as `init`, `workspace upgrade`, and semantic setup apply will call a shared idempotent ensure-runtime path by default. That path can install and start the background worker while surfacing what happened in normal command output and UI state.

### Decision: Service policy is operator-visible and reversible
Workspace-local state will record whether the background runtime is operator-disabled or managed-by-default. CLI and UI controls must both read and write the same policy and lifecycle state.

### Decision: Overview should summarize memory state and dream effects, not just counts and events
Operators need a readable answer about:

- current memory mix and active states
- whether low-signal or stale patterns dominate
- what the latest dream or semantic cycle actually changed

That summary belongs in `/api/overview` and the overview UI, backed by existing mutation audits and durable-memory state.

### Decision: Managed runtime must be semantic-aware, not transcript-only
Semantic-first workspaces frequently accumulate explicit events without transcript episode files. The managed worker therefore cannot treat transcript backlog as the only source of dream work. Auto mode must resolve from workspace posture and, when semantic or hybrid posture is active, use explicit-event signal as a first-class backlog source for semantic cycles.

### Decision: Runtime health and semantic materialization need separate diagnostics
Operators must be able to distinguish:

- the service is installed/running
- the worker is polling
- semantic signal is present
- the semantic path is blocked
- the semantic path consumed signal but did not materialize learned context yet

That diagnosis should live in one shared read model used by `service status`, `/api/overview`, `/settings`, and `/overview` so the CLI and UI do not drift.

## Risks / Trade-offs

- background-runtime defaults could conflict with earlier "no daemon mental overhead" work if the UI or CLI becomes more complex
  - mitigation: expose one high-signal ensure/disable story while keeping advanced service commands available
- operators may misread "runtime running" as "semantic value is healthy"
  - mitigation: keep runtime state distinct from semantic readiness and memory-quality diagnostics
- event-driven semantic work could repeatedly churn on the same signal
  - mitigation: persist the latest consumed semantic signal timestamp/source so the worker can distinguish pending signal from already-consumed signal
- digestible summaries could drift from raw evidence
  - mitigation: derive them from observability index data and mutation audits, and preserve links to the detailed routes

## Migration Plan

1. add explicit runtime policy and ensure-runtime control paths
2. teach primary commands to use that path
3. make the managed worker semantic-aware for explicit-event backlog and auto mode
4. extend overview/api/ui with runtime, semantic-pipeline, and memory-surface summaries
5. document the new primary-path behavior and verification commands
