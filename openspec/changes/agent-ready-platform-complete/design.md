# design.md — agent-ready-platform-complete

## Context

OpenDream already ships a local-first memory runtime, activation, service lifecycle, and automation projections (`435-opendream-automations`). The architect bundle `436-agent-ready-platform-complete` adds an **agent-readiness control plane**: thin distributable shims, path-scoped guidance, stable JSON contracts, MCP inventory enforcement, an automation engine registry, guidance-drift proposals, isolated worktrees for code mutation, and release gates.

The OpenSpec CLI requires change directory names to start with a letter; this change lives at `openspec/changes/agent-ready-platform-complete/` while the registry spec id remains `436-agent-ready-platform-complete`.

## Goals / Non-Goals

**Goals:**

- Canonical policy stays in repo-owned docs; vendor surfaces are generated or thin references.
- Machine-readable `opendream contract export` with schema-validated fixtures.
- Path-scoped `AGENTS.md` (and related) for `opendream/`, `openspec/`, `.meta/spec-adapters/`, `tests/`.
- Registry and ADR placeholders so promotion and verification have a home.

**Non-Goals (this increment):**

- Full package generators, engine registry execution, worktree isolation, and guidance-drift engines (tracked as remaining tasks in `tasks.md`).

## Decisions

1. **Contract export v1** — Static inventory (top-level commands from `build_parser()`, schema file list, version map, placeholder engine/package lists) plus example payload hashes. Workspace is accepted for CLI symmetry; v1 export does not vary by workspace content.
2. **Fragmented design docs** — Keep detailed design under `design/*.md`; this file satisfies the spec-driven `design.md` artifact and points to those fragments.
3. **MCP inventory** — Document that the core runtime is stdlib-only; optional MCP servers are operator-local (editor/IDE). Required fields are filled with explicit “not used by default” where applicable.

## Risks / Trade-offs

- **Registry / export drift** — If a new top-level CLI command is added but contract tests do not run, export can become incomplete. Mitigation: `test_contract_export_matches_fixture` and optional command-list assertion.
- **Large remaining scope** — Most WS5–WS9 tasks remain open; this increment lands planning artifacts + WS1–WS3 partial + MCP doc hardening.

## Migration Plan

1. Land OpenSpec change + registry entry (`proposed` → `active` when implementation catches up).
2. Follow `tasks.md` workstreams; bump `cli_output_version` / fixtures when export shape changes.

## Open Questions

- Exact JSON schema for engine registry manifests and package metadata (deferred to WS5–WS6).
- Whether MCP inventory should gain a machine-readable JSON mirror in-repo (T14).

## Detailed design fragments

See `design/00-architecture.md` through `design/07-migration-and-rollout.md` in this change directory.
