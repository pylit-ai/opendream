# OpenSpec

Use this directory for proposal-stage change bundles before they become canonical repo specs.

## Workflow
1. Draft a self-contained change under `openspec/changes/<id>/`.
2. Keep rationale, schemas, prompts, config, evals, and verification with the change.
3. Link to canonical repo policy instead of copying it.
4. When a proposal is approved for implementation, translate accepted behavior into `specs/<id>/{spec.md,plan.md,tasks.md}` and update `specs/registry.yaml`.

## Boundaries
- `specs/` remains the canonical implementation surface.
- `openspec/` is for proposal bundles, research handoff, and pre-implementation design work.
- Repo-wide rules stay in `CONSTITUTION.md`, `AGENTS.md`, and `docs/governance/DOCS_SYSTEM.md`.

## Review checklist
- Proposal scope is explicit.
- Acceptance and verification are testable.
- Storage and safety boundaries are clear.
- Promotion path to `specs/` is obvious.
