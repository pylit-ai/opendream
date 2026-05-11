# ADR-014: Execution ownership matrix

## Status
Accepted

## Context
With multiple execution surfaces (direct-provider, codex-account, claude-scheduled-task, cursor-automation, deterministic), operators needed a single source of truth for who owns each semantic execution run and what trust controls apply. Without an explicit matrix, docs could drift from runtime, and status surfaces could show stale or inaccurate ownership information.

## Decision
Execution ownership is a first-class runtime concept with the following invariants:

1. **Every semantic run records its execution owner** — one of `opendream-local` or `vendor-runtime`.
2. **Status, contract export, and observability surfaces always show the active owner**, the auth source, and the trust boundary.
3. **Docs use the same vocabulary as runtime** — "OpenDream owns" vs "vendor owns" vs "deterministic (no model call)".
4. **The advanced-runtime report checks memory-excellence evidence across all supported execution modes**, not just the one the developer happens to use locally.

| Surface | Shows execution owner | Shows auth source | Shows trust boundary |
|---|---|---|---|
| `semantic status` | yes | yes | yes |
| `dream status` | yes | yes | no |
| `contract export` | yes (adapter inventory) | yes (auth matrix) | yes |
| `observability index` | yes | yes | yes |
| README / FAQ / docs | yes (execution matrix) | yes | yes |

## Consequences
- Operators can audit who ran a semantic pass by inspecting status or observability surfaces.
- Release claims are verifiable against the advanced-runtime report.
- Docs and runtime stay aligned because both reference the same adapter manifests.
