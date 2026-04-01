# plan.md — 440-advanced-memory-platform-release-bundle

## Summary

Implement the complete release layer that unifies memory excellence with operator-grade execution surfaces. OpenDream remains the canonical memory/control plane. Semantic work may be executed by:
- OpenDream directly through configured providers,
- Codex on trusted local/private infrastructure,
- Claude Code through scheduled tasks,
- Cursor through automations,
- or deterministic fallback.

This bundle makes those paths explicit, auditable, benchmarked, and correctly documented.

## Architecture impact

### Touched components
- `opendream/cli.py`
- `opendream/semantic_dreamer.py`
- `opendream/provider_registry.py`
- `opendream/storage.py`
- `opendream/validation.py`
- `opendream/models.py`
- `opendream/automation.py`
- `opendream/evaluation.py`
- `opendream/contract_export.py`
- `opendream/observability.py`
- `opendream/webapp.py`
- `scripts/verify.py`
- `scripts/release_check.py`
- `.meta/spec-adapters/claude-code/`
- `.meta/spec-adapters/codex/`
- `.meta/spec-adapters/cursor/` (new)
- `docs/automation/dream-task-playbook.md`
- `docs/automation/examples/feature-mining.md`
- `docs/coding-agents.md`
- `docs/FAQ.md`
- `docs/architecture/overview.md`
- `docs/benchmarks/methodology.md`
- `docs/benchmarks/autodream-comparison.md`
- `README.md`
- `CHANGELOG.md`
- relevant tests / fixtures / contract snapshots

### New major surfaces
- semantic execution-policy resolver
- setup wizard and semantic strategy report
- adapter manifests and status reports for Codex / Claude / Cursor
- delegated semantic envelope and inbox/ingest pipeline
- adapter-specific feature-mining and semantic-refresh scaffold generators
- advanced-runtime report that merges execution-mode evidence with the memory-excellence scorecard

### Explicit dependencies
This bundle assumes the memory-excellence bundle is present or lands first. Its guarantees are relied on, not redefined:
- verified writes
- grep-first transcript probing
- generated-only compatibility views
- contradiction/relation graph
- reconciliation sweeps
- procedural memory upgrades
- memory-excellence scorecard

### Unchanged fundamentals
- typed durable state remains canonical
- markdown views remain generated from canonical state
- adapters remain non-normative thin surfaces
- unsupported OAuth piggybacking remains forbidden
- no background memory worker writes product code

## Data model / contract changes
- extend semantic config with:
  - `requested_preference`
  - `active_execution_strategy`
  - `candidate_strategies`
  - `active_adapter_id`
  - `fallback_policy`
- add semantic adapter manifest/status schemas
- add delegated semantic envelope schema
- add semantic setup report schema
- add advanced-runtime report schema
- extend contract export with execution ownership and adapter inventory

## Interfaces

### New CLI
- `opendream semantic setup --workspace <ws> [--prefer no-extra-key|direct-provider]`
- `opendream semantic adapters list`
- `opendream semantic adapters detect --workspace <ws>`
- `opendream semantic adapters scaffold --workspace <ws> --adapter <id>`
- `opendream semantic adapters status --workspace <ws>`
- `opendream semantic ingest --workspace <ws> [--path <file>|--scan-inbox]`
- `opendream automation scaffold-dream --workspace <ws> --adapter <id> --kind feature-radar|bug-radar|fix-radar|semantic-refresh`

### Extended CLI
- `opendream semantic status`
- `opendream dream status`
- `opendream prepare-context`
- `opendream contract export`
- release-check and verify commands

## Observability
- show semantic execution owner, auth source, trust notes, and last adapter health
- show delegated envelopes pending / ingested / failed
- show adapter-generated semantic refresh status next to memory-excellence diagnostics
- keep review UX consistent between local and delegated execution

## Security / safety review
- codex account-backed mode is restricted to trusted local/private infrastructure
- Claude/Cursor delegated modes are treated as vendor-owned execution, not token-sharing
- delegated envelopes validate before ingest and cannot directly mutate canonical truth
- setup wizard must never recommend unsupported Gemini OAuth reuse
- docs must not imply generic session borrowing or hidden auth magic

## Rollout
1. land execution-policy and setup schemas
2. land setup wizard and strategy detection
3. land Codex adapter
4. land Claude adapter
5. land Cursor adapter
6. land delegated envelope ingest
7. land feature-mining and semantic-refresh scaffolds
8. land docs / release-note / benchmark truthfulness updates
9. land advanced-runtime report and release gates

## Rollback
1. disable adapter-backed semantic execution
2. retain direct-provider and deterministic paths
3. preserve delegated envelopes and reports for inspection
4. keep docs honest about the reduced surface area

## Verification plan
- unit tests for setup resolution, adapter detection, status reporting, envelope validation
- integration tests for Codex / Claude / Cursor scaffolds
- integration tests for delegated ingest and feature-mining scaffolds
- contract export tests
- docs and release-note wording checks
- advanced-runtime report tests
- `make verify` and `make release-check` include cross-mode memory-excellence checks

## ADRs required
Yes. Promote enduring decisions on:
- semantic execution ownership matrix
- delegated ingest model
- Codex account-backed trust boundary
- unsupported-path policy
- advanced-runtime proof contract
