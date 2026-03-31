# plan.md — 436-agent-ready-platform-complete

## Summary
Implement the complete agent-ready platform layer on top of the current OpenDream runtime. Keep canonical behavior in repo-owned docs and schemas, keep vendor integrations thin and installable, and ensure unattended automation remains auditable and reversible.

## Architecture impact

### Touched components
- `opendream/cli.py`
- `opendream/automation.py`
- `opendream/activation.py`
- `opendream/adapter_loader.py`
- `opendream/adapter_profiles.py`
- `opendream/service.py`
- `opendream/storage.py`
- `opendream/validation.py`
- `opendream/observability.py`
- `opendream/webapp.py`
- `docs/coding-agents.md`
- `docs/mcp/servers.md`
- `docs/architecture/overview.md`
- `AGENTS.md`
- nested `AGENTS.md` or equivalent path-scoped guidance files
- `.meta/spec-adapters/*`
- generated plugin/package directories
- tests and verification scripts

### New major surfaces
- declarative engine registry for automation `skill_ref`
- built-in and plugin-backed automation engines
- generated machine-readable contract export
- plugin/package generation for supported ecosystems
- isolated worktree runner and provenance model
- guidance-drift analyzers and proposal emitters
- agent-readiness conformance checks

### Unchanged fundamentals
- canonical policy precedence
- local-first default memory behavior
- separation between durable memory and automation projection outputs
- requirement that unattended background memory maintenance does not mutate product code unless explicitly expanded

## Data model / contract changes
- add engine-registry state and manifest validation
- add plugin package manifests and generation metadata
- add contract export schema and example fixtures
- extend automation job schema with execution isolation metadata and engine resolution metadata
- extend automation run reports with provenance for engine, worktree, approvals, and proposal outputs
- add guidance-drift proposal records and review state

## Interfaces
- new CLI groups for plugin/package generation, contract export, engine registry inspection, and worktree execution management
- extended `opendream automation register|run|tick|status|review|promote|reject`
- generated vendor package outputs for Codex, Claude Code, Cursor, and GitHub Copilot
- new conformance and contract verification commands

## Observability
- all engine resolution and plugin-generation flows emit structured reports
- automation run reports include engine id, package source, execution isolation mode, and worktree id when applicable
- guidance-drift analyzers emit deterministic summaries and machine-readable proposal artifacts
- contract export includes `cli_output_version`, schema version map, and example payload hashes

## Security / safety review
- plugin/package generation must stay non-normative and point back to canonical sources
- arbitrary third-party skills must not execute in unattended automation until admitted through the engine registry
- code-mutating automation runs require isolated worktree mode plus explicit approval policy
- MCP inventory must document auth model, exposed tools/resources, trust boundaries, and revocation path
- guidance-drift proposals must remain reviewable projections until a human or explicit promotion command accepts them

## Rollout
1. land schemas, engine registry, and contract export
2. land nested/path-scoped guidance and MCP inventory
3. land plugin/package generators and adapter conformance tests
4. land guidance-drift automations
5. land isolated worktree execution and approval gates
6. land end-to-end release gates and docs
7. run full verification and manual matrix

## Rollback
1. disable new plugin/package generation commands
2. disable engine registry-backed automation engines
3. keep existing memory runtime and current `435` automation layer intact
4. preserve generated artifacts for debugging but remove activation paths
5. retain docs updates that do not conflict with rollback safety

## Verification plan
- unit tests for schemas, registry resolution, guidance scoring, and worktree policies
- integration tests for plugin generation, contract export, engine-backed automation execution, and isolated runs
- end-to-end tests for Codex / Claude / Cursor / Copilot package generation and smoke validation
- manual checks for generated package installation in temp repos
- `make verify` must include all new conformance checks

## ADR needed?
Yes. Promote enduring decisions on:
- plugin/distribution architecture
- engine registry design
- isolated code-mutation execution
- guidance-drift proposal lifecycle
