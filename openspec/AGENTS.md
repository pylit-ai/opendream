# OpenSpec — agents

## Purpose

Path-scoped entry for work under `openspec/`. Root `AGENTS.md` remains the routing index; OpenSpec workflow rules and promotion live here and in the change registry.

## Read order

1. This file (scope and pointers)
2. `docs/governance/DOCS_SYSTEM.md`
3. `CONSTITUTION.md`
4. Active change under `openspec/changes/<name>/` (proposal → specs → design → tasks)

## Conventions

- **Changes** live in `openspec/changes/`. Change directory names must start with a letter (OpenSpec CLI constraint); registry ids may use numeric prefixes (e.g. `436-agent-ready-platform-complete`).
- **Canonical spec bundles** promoted from changes live under `specs/<id>/` at repo root when implemented.
- Use `openspec status --change "<name>"` and `openspec instructions …` for artifact flow.

## Active platform slice

Agent-ready platform planning: `openspec/changes/agent-ready-platform-complete/` (registry id `436-agent-ready-platform-complete`).
