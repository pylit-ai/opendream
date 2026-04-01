# 05-contradiction-graph-and-relations.md

## Goal
Make contradictions and supersession central to memory reasoning.

## Relation edge types
- `supports`
- `conflicts_with`
- `supersedes`
- `derived_from`
- `verified_by`
- `invalidated_by`

## Usage
- retrieval ranking uses relation penalties/boosts
- review UI shows clusters, not isolated notes
- promotion logic uses relation state to decide active vs contested vs superseded
- contradiction metrics are explicitly measured

## Important rule
OpenDream does not need a full graph database to exploit relations well. A bounded, auditable relation layer is enough for this release.
