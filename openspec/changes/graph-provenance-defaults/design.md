## Context

The current graph builder assembles edges from memory records, retrievals, runs, annotations, and reviews, but it does not project the richer durable relation-edge store into the graph payload. The default `/graph` request also arrives with no focus, which makes the API return the first `limit` nodes rather than a bounded neighborhood. In practice that produces a visually serial canvas even when the underlying lineage is more interesting.

## Goals / Non-Goals

**Goals:**
- Surface durable memory-to-memory provenance edges such as `derived_from`, `supports`, `verified_by`, and persisted `supersedes` in the graph payload.
- Make the initial graph load focus on a meaningful memory neighborhood with a bounded default depth.
- Preserve the existing graph controls and keep hierarchical layout as the default lineage view.
- Cover the behavior with deterministic tests.

**Non-Goals:**
- Redesign the graph UI beyond default landing behavior.
- Introduce a new memory model or hierarchical-memory subsystem.
- Change the force-layout implementation or add new dependencies.

## Decisions

- Build graph memory-to-memory edges from `relation_edges.json` first, then supplement from inline memory fields only when a relation edge is missing. This keeps the graph aligned with the durable provenance store and avoids duplicate edges.
- Ignore relation edges whose endpoints are absent from the current observability memory set. This preserves local inspectability and avoids dangling graph nodes.
- Change `/graph` and `/api/graph` defaults to select the most recently updated memory as the initial focus when the caller does not provide one. This preserves explicit focus overrides while making the landing state neighborhood-based by default.
- Keep `hierarchical` as the default layout and raise the default depth from `1` to `2` only for the focused default state. This improves interpretability without replacing lineage semantics with force-directed positioning.

## Risks / Trade-offs

- [Graph becomes denser than before] → Keep focus required by default and preserve existing node limits.
- [Persisted relation edges and inline lineage disagree] → Prefer persisted relation edges because they are the durable provenance store, but keep existing inline fields as a fallback for older data.
- [Operators expect the old unfocused landing page] → Preserve explicit URL parameters so existing deep links and manual views still work.
