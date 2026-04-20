## ADDED Requirements

### Requirement: Graph payload includes durable provenance relations
The observability graph payload SHALL include durable memory-to-memory relation edges from the relation-edge store for supported provenance kinds, and it MUST avoid duplicating equivalent inline lineage edges when both sources describe the same relation.

#### Scenario: Derived provenance creates branches
- **WHEN** the relation-edge store contains multiple `derived_from` edges from different memories to the same parent memory
- **THEN** the graph payload includes all of those edges
- **AND** the hierarchical layout input can represent the branch as sibling nodes at the same rank

#### Scenario: Inline lineage remains as fallback
- **WHEN** a memory record declares `supersedes` or `conflicts_with` relations that are not present in the relation-edge store
- **THEN** the graph payload still includes those relations
- **AND** it does not emit duplicates when the persisted relation-edge store already contains the same relation

### Requirement: Default graph landing state is neighborhood-based
The graph route and graph API SHALL default to a focused neighborhood view when the caller does not provide an explicit focus, using the most recently updated durable memory as the initial focus and a bounded default depth.

#### Scenario: Graph route defaults to a focused memory
- **WHEN** an operator opens `/graph` without query parameters
- **THEN** the rendered page state targets the most recently updated durable memory as the focus
- **AND** the default depth is greater than zero so the initial view shows a neighborhood rather than an isolated node

#### Scenario: Explicit query parameters override defaults
- **WHEN** the caller provides `focus`, `depth`, or `layout` query parameters
- **THEN** the graph route and graph API honor those explicit values instead of the defaults
