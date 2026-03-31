## Why

OpenDream's memory runtime scores 89/100 and the performance improvements are implemented, but the project cannot credibly claim release-readiness or AutoDream superiority without closing three gaps: (1) the performance evaluation is standalone instead of integrated into the default verification path, (2) there is no reproducible AutoDream comparison harness, and (3) several release-critical items from the 436 platform bundle remain open. AutoDream is now publicly confirmed as a 4-phase consolidation pipeline (orient, gather, consolidate, prune) running every ~24h — OpenDream already exceeds it on concurrency safety, audit trails, contradiction handling, and procedural memory, but these advantages are not yet provable via automated benchmarks or documented for external scrutiny.

## What Changes

- Integrate `eval performance` into `make verify` so the performance scorecard is part of release proof, not a side experiment
- Build a reproducible AutoDream comparison harness with documented methodology, repeated trials, and machine-readable outputs
- Expand the eval corpus beyond fixture-only to include realistic task diversity (small OSS repo, medium app repo, docs-heavy repo patterns)
- Wire the performance scorecard into `make release-check` so failure to meet threshold (>=80) blocks release
- Document verifiable improvements over AutoDream with honest limitations and negative results
- Reconcile spec-state drift between `specs/registry.yaml` and canonical spec files
- Produce clean-machine release evidence artifacts
- Close the remaining 436 P0 blockers that affect release credibility: MCP conformance gate (T14-T15, T17), engine registry basics (T27-T33), and package generation smoke tests (T18-T26)
- Add benchmark methodology documentation and a "skeptical engineer" FAQ
- Ensure the quickstart path works in under 5 minutes for a new user

## Capabilities

### New Capabilities
- `autodream-comparison-harness`: Reproducible benchmark harness for fair OpenDream vs AutoDream comparison — methodology doc, task set, repeated trials, cost/latency accounting, failure taxonomy, machine-readable outputs
- `integrated-performance-gate`: Performance evaluation integrated into `make verify` and `make release-check` as a blocking release gate with scorecard archival
- `release-evidence`: Clean-machine verification evidence workflow — archived manifests from multiple environments, linked from release notes
- `benchmark-documentation`: Public benchmark methodology, reproducibility instructions, honest limitations, negative results, and skeptical-engineer FAQ

### Modified Capabilities
- `420-truthful-verification-and-release`: Add performance harness as a required verification stage; add scorecard to release manifest
- `435-opendream-automations`: Reconcile registry status with actual implementation state for governance hygiene

## Impact

- **Verification pipeline**: `make verify` gains a performance-eval stage; `make release-check` archives scorecard alongside existing manifest
- **Test fixtures**: New eval corpus entries for task diversity beyond current deterministic fixtures
- **Documentation**: New `docs/benchmarks/` tree with methodology, results, and reproduction instructions; FAQ document
- **Specs governance**: Registry reconciliation pass across `specs/` to eliminate status drift
- **436 dependencies**: Partial advancement of WS4 (MCP conformance), WS5 (package smoke), WS6 (engine registry) — scoped to P0 release blockers only, not full platform completion
- **CI/release**: Performance threshold becomes a release gate; scorecard artifact added to release manifest schema
