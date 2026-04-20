## Why

The graph view currently defaults to an unfocused hierarchical slice that often looks like a single serial chain, even when richer provenance relationships exist elsewhere in the memory store. This makes the graph hard to interpret and undersells the review tooling that is supposed to expose focused, auditable lineage.

## What Changes

- Include durable relation-edge provenance in the graph payload instead of relying only on inline memory lineage fields.
- Prefer focused neighborhoods for the default graph landing state so operators see a meaningful local subgraph instead of an arbitrary first-page slice.
- Keep hierarchical layout as the default for lineage inspection while allowing force layout as an explicit operator choice.
- Add verification for graph payload composition and default graph route behavior.

## Capabilities

### New Capabilities
- `graph-provenance-view`: Graph payloads and the default graph landing state surface durable provenance neighborhoods instead of arbitrary serial slices.

### Modified Capabilities

## Impact

- Affected code: `opendream/observability.py`, `opendream/webapp.py`, `opendream/static/graph.js`, graph-related tests
- Affected system: observability graph API and browser graph route behavior
- Dependencies: none
