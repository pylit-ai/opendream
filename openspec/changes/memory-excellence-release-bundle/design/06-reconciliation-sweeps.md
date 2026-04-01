# 06-reconciliation-sweeps.md

## Goal
Treat staleness and storage drift as first-class maintenance work.

## Sweep coverage
- renamed or moved project roots
- orphaned compat views
- stale topic files whose support has vanished or been superseded
- dead record references
- missing file/path references in procedural memory
- memory-root drift and activation mismatches

## Outcomes
- `ok`
- `regenerated`
- `downgraded`
- `quarantined`
- `needs_review`

## Rules
- reconciliation never silently destroys provenance
- repairs are bounded and auditable
- destructive cleanup requires explicit policy and audit note
