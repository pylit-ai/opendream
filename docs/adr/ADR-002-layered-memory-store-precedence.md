# ADR-002: Layered Memory Store Precedence

## Status
Accepted

## Context
OpenDream started as a workspace-local memory runtime. Real operators need repo-local memory and a user-global store without collapsing those boundaries or adding hidden state.

## Decision
- OpenDream supports distinct `project` and `global` store kinds.
- `prepare-context`, `maintain`, `status`, and `tick` may operate on an ordered store group.
- Default precedence is `project` before `workspace`, `agent`, and `global`.
- When project and global memory share the same durable key, project memory suppresses the lower-precedence global duplicate in composed context.
- Sensitive events MUST NOT be routed into the global store.
- Multi-store execution remains filesystem-backed, local-first, and explicit through CLI flags or a store manifest.

## Consequences
- Operators can keep reusable preferences in `~/.opendream-global` while preserving repo-local overrides.
- Adapter packs can compose context through one CLI surface instead of inventing framework-specific memory policy.
- Store composition stays auditable because each store keeps its own event, candidate, durable, and audit artifacts.
