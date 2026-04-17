# AGENTS.md

## Purpose
This is the canonical entrypoint for coding agents in this repository.
Do not treat this file as the full source of truth.
Use it to find the correct source of truth.

## Read order

### If drafting or reviewing an OpenSpec proposal
1. `openspec/AGENTS.md`
2. `docs/governance/DOCS_SYSTEM.md`
3. `CONSTITUTION.md`

### If changing repository structure, docs, or agent configuration
1. `docs/governance/DOCS_SYSTEM.md`
2. `CONSTITUTION.md`
3. `AGENTS.md`

### If changing product direction or tradeoffs
1. `NORTHSTAR.md`
2. `PRD.md`
3. `CONSTITUTION.md`

### If implementing or modifying a feature
1. active `specs/<id>/spec.md`
2. active `specs/<id>/plan.md`
3. active `specs/<id>/tasks.md`
4. `CONSTITUTION.md`
5. path-scoped `AGENTS.md` for the subtree you are editing (`opendream/`, `openspec/`, `.meta/spec-adapters/`, `tests/`)
6. relevant path-scoped rules and skills

### If touching legacy code and `CURRENT_STATE.md` exists
1. `CURRENT_STATE.md`
2. `MIGRATION_GUARDRAILS.md`
3. active spec bundle
4. `CONSTITUTION.md`

## Path-scoped guidance
- `opendream/AGENTS.md` — runtime / CLI / schema conventions
- `openspec/AGENTS.md` — OpenSpec change workflow under `openspec/`
- `.meta/spec-adapters/AGENTS.md` — thin adapter payloads vs canonical policy
- `tests/AGENTS.md` — verification and fixture conventions

## Core docs
- `NORTHSTAR.md` — enduring product vision and non-goals
- `CONSTITUTION.md` — project-wide invariants and safety rules
- `PRD.md` — current product / epic scope
- `docs/governance/DOCS_SYSTEM.md` — documentation taxonomy and precedence
- `openspec/AGENTS.md` — OpenSpec proposal workflow and promotion rules
- `docs/architecture/overview.md` — enduring technical structure
- `docs/automation/dream-task-playbook.md` — reproducible pattern for dream automations (capture, projection jobs, optional semantic refresh)
- `docs/automation/complete-operator-workflow.md` — copy-paste command sequences: feature radar, hybrid dream smoke, Layer C / delegated AI refresh; where LLMs run vs heuristics
- `docs/automation/semantic-mode-and-feature-radar-setup.md` — operator walkthrough: hybrid/semantic dream config, provider files, and feature-radar automation
- `docs/mcp/servers.md` — MCP servers, tool contracts, and trust boundaries
- `specs/registry.yaml` — active / superseded / archived change registry

## Canonical vs adapters
- Canonical implementation requirements live only in `specs/<id>/{spec.md,plan.md,tasks.md}` and lifecycle metadata in `specs/registry.yaml`.
- Durable architectural rationale belongs in `docs/adr/`; durable technical references belong in canonical docs under `docs/`.
- Framework-specific artifacts are optional adapters and must only translate canonical sources.
- Preferred location for framework adapter payloads is `.meta/spec-adapters/<framework>/...`.

## Skills (on-demand)
- **repo-os-greenfield-bootstrap** — After `copier copy`, run this to fill NORTHSTAR/PRD/specs placeholders and align commands.
- **opendream-dream-automation** — Wire OpenDream capture, automation projection jobs, and optional semantic refresh (feature/bug/fix radar and similar). Canonical prose: `docs/automation/dream-task-playbook.md`.

## Commands
- setup: `make setup`
- dev: `make dev`
- test: `make test`
- lint: `make lint`
- typecheck: `make typecheck`
- verify: `make verify`

## Approval boundaries
Stop and request explicit approval before:
- destructive data operations
- auth / permission changes
- billing-affecting changes
- schema migrations
- production config changes
- secret rotation

## Rules
- For non-trivial work, do not implement before reading the active spec bundle.
- Prefer minimal diffs.
- Do not invent new documentation categories when an existing canonical home exists.
- If documentation appears to conflict, follow precedence from `docs/governance/DOCS_SYSTEM.md`.
- Update the spec and impacted docs when behavior changes.
