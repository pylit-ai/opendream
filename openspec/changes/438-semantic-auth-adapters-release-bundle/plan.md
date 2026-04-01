# plan.md — 438-semantic-auth-adapters-release-bundle

## Summary
Implement the release-complete operator layer for semantic mode. Make authentication and execution paths explicit, prefer no-extra-key execution when supported by a vendor runtime, and ensure vendor-delegated semantic runs return structured, reviewable artifacts into OpenDream.

## Architecture impact

### Touched components
- `opendream/cli.py`
- `opendream/semantic_dreamer.py`
- `opendream/provider_registry.py`
- `opendream/contract_export.py`
- `opendream/observability.py`
- `opendream/webapp.py`
- `opendream/storage.py`
- `opendream/validation.py`
- `opendream/semantic_setup.py` (new)
- `opendream/semantic_adapters.py` (new)
- `opendream/semantic_ingest.py` (new)
- `opendream/schema/semantic-adapter-manifest.schema.json` (new)
- `opendream/schema/semantic-adapter-status.schema.json` (new)
- `opendream/schema/semantic-setup-report.schema.json` (new)
- `opendream/schema/delegated-semantic-envelope.schema.json` (new)
- `opendream/schema/semantic-execution-policy.schema.json` (new)
- `.meta/spec-adapters/codex/...`
- `.meta/spec-adapters/claude-code/...`
- `.meta/spec-adapters/cursor/...` (new)
- `docs/automation/dream-task-playbook.md`
- `docs/coding-agents.md`
- `docs/FAQ.md`
- `docs/benchmarks/autodream-comparison.md`
- `README.md`
- `CHANGELOG.md`
- release evidence / release-check scripts
- tests and fixtures

### New major surfaces
- semantic execution policy resolver
- semantic adapter registry and manifests
- delegated semantic envelope + ingest pipeline
- setup wizard and account-backed recommendation engine
- adapter-specific scaffolding/generation
- auth/status matrix in CLI + observability + contract export
- release-note/doc honesty gates

### Unchanged fundamentals
- durable memory remains canonical
- learned context remains non-canonical until promoted through verification/promotion policy
- direct-provider mode remains supported where operators want it
- unsupported OAuth piggybacking remains forbidden

## Data model / contract changes
- semantic config grows explicit `execution_strategy`, `preferred_auth_mode`, `active_adapter`, and `fallback_policy`
- adapter manifests declare trust boundary, execution owner, auth source, local-file capability, scheduling durability, and ingest method
- delegated semantic runs use a structured envelope artifact that can be validated and ingested
- status/contract export include active strategy, candidate strategies, last adapter health, and next recommended operator action

## Interfaces

### New CLI
- `opendream semantic setup --workspace <ws> [--prefer no-extra-key|direct-provider]`
- `opendream semantic adapters list`
- `opendream semantic adapters detect --workspace <ws>`
- `opendream semantic adapters scaffold --workspace <ws> --adapter <id>`
- `opendream semantic adapters status --workspace <ws>`
- `opendream semantic adapters validate --workspace <ws>`
- `opendream semantic ingest --workspace <ws> [--path <envelope>|--scan-inbox]`

### Extended CLI
- `opendream semantic status` shows execution/auth matrix and active strategy
- `opendream dream status` includes semantic owner and delegated/local run metadata
- `opendream contract export` includes adapter inventory and auth matrix

## Observability
- expose active semantic execution strategy in status + web/read-model views
- show whether semantic work is owned by:
  - local direct-provider execution
  - Codex local account execution
  - Claude delegated task execution
  - Cursor delegated automation execution
  - deterministic fallback
- show last success/failure reason and trust boundary notes

## Security / safety review
- treat `~/.codex/auth.json` as sensitive material; never log or commit it
- do not recommend unsupported third-party OAuth reuse
- prefer vendor-owned scheduling/runtime surfaces over token borrowing
- delegated envelopes must be schema-validated before ingest
- repo-writing delegated adapters must use isolated or clearly bounded artifact paths, never arbitrary memory mutation

## Rollout
1. land execution/auth policy model and schemas
2. land setup wizard and adapter detection/status
3. land Codex account adapter
4. land Claude scheduled-task adapter
5. land Cursor automation adapter
6. land delegated envelope ingest pipeline
7. land docs / release notes / FAQ / benchmark copy fixes
8. land release gates and manual validation matrix

## Rollback
1. disable adapter-backed semantic execution
2. retain deterministic and direct-provider modes
3. keep delegated-ingest artifacts inert
4. keep docs honest about reduced feature surface

## Verification plan
- schema validation tests
- adapter detection and setup tests
- contract export tests
- delegated envelope ingest tests
- fixture-based adapter smoke tests
- documentation honesty checks
- release-check gate ensuring setup text and runtime behavior agree

## ADR needed?
Yes. Promote enduring decisions on:
- auth/execution matrix
- delegated ingest model
- Codex account-auth trust boundary
- unsupported OAuth reuse policy
