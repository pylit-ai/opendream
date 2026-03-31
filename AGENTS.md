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
5. relevant path-scoped rules and skills

### If touching legacy code and `CURRENT_STATE.md` exists
1. `CURRENT_STATE.md`
2. `MIGRATION_GUARDRAILS.md`
3. active spec bundle
4. `CONSTITUTION.md`

## Core docs
- `NORTHSTAR.md` — enduring product vision and non-goals
- `CONSTITUTION.md` — project-wide invariants and safety rules
- `PRD.md` — current product / epic scope
- `docs/governance/DOCS_SYSTEM.md` — documentation taxonomy and precedence
- `openspec/AGENTS.md` — OpenSpec proposal workflow and promotion rules
- `docs/architecture/overview.md` — enduring technical structure
- `docs/mcp/servers.md` — MCP servers, tool contracts, and trust boundaries
- `specs/registry.yaml` — active / superseded / archived change registry

## Canonical vs adapters
- Canonical implementation requirements live only in `specs/<id>/{spec.md,plan.md,tasks.md}` and lifecycle metadata in `specs/registry.yaml`.
- Durable architectural rationale belongs in `docs/adr/`; durable technical references belong in canonical docs under `docs/`.
- Framework-specific artifacts are optional adapters and must only translate canonical sources.
- Preferred location for framework adapter payloads is `.meta/spec-adapters/<framework>/...`.

## Skills (on-demand)
- **repo-os-greenfield-bootstrap** — After `copier copy`, run this to fill NORTHSTAR/PRD/specs placeholders and align Commands. Claude: use `.claude/commands/bootstrap-repo` or repo-bootstrapper subagent.

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

<!-- metactl:begin agents-md -->
# Repository Builder

Target: Codex CLI
Policy: Brownfield Safe Builder

Prefer retrieval-led reasoning: use this file as a compact index, then open the referenced pack body that matches the task.

## Active Pack Index
Mode: reference_index
- Authoring metactl artifacts and prompt systems (`wxb-pack-authoring`): Scaffold commands, skills, rules, workflows; prompt optimization; generalize prompts; generate commands/skills from SOTA docs; preserve skills globally; mine transcripts for automation; steward wx-b metactl-library growth and metactl v2alpha compatibility.
  Open for: meta, authoring, automation, library, maintenance, pack:authoring
  Bodies:
  - Meta-skill: Create a metactl Command: `skills/wxb-pack-authoring/skill/SKILL.md`
  - Meta-skill: Create or Maintain metactl Rules: `skills/wxb-pack-authoring/skill-2/SKILL.md`
  - Meta-skill: Create a metactl Skill: `skills/wxb-pack-authoring/skill-3/SKILL.md`
  - Meta-skill: Create a metactl Workflow: `skills/wxb-pack-authoring/skill-4/SKILL.md`
  - Meta prompt optimization: `skills/wxb-pack-authoring/skill-5/SKILL.md`
  - Meta prompt optimization (strict): `skills/wxb-pack-authoring/skill-6/SKILL.md`
  - Generalize Prompt (Meta-Prompting Skill): `skills/wxb-pack-authoring/skill-7/SKILL.md`
  - Generate Commands and Skills from SOTA Prompting: `skills/wxb-pack-authoring/skill-8/SKILL.md`
  - Skill Preserve: `skills/wxb-pack-authoring/skill-9/SKILL.md`
  - Workflow Miner: `skills/wxb-pack-authoring/skill-10/SKILL.md`
  - metactl-library steward: `skills/wxb-pack-authoring/skill-11/SKILL.md`
- Charter audit Cursor harness (command + rule) (`wxb-pack-charter-harness`): Slash command and Cursor rule backing /agent-charter-audit; pairs with wxb-pack-core-quality agent-charter-audit SKILL.md. Emitted by metactl compile for targets that project command/rule pack resources.
  Open for: governance, meta, cursor, charter-audit, pack:governance
  Bodies:
  - Charter audit Cursor harness (command + rule): `skills/wxb-pack-charter-harness/skill/SKILL.md`
- CLI UX, DevEx, and audit harness (`wxb-pack-cli-devex`): Dogfood audits, read-only and exec CLI reviews, human sim harnesses, OpenSpec backlog export, and UX/DevEx testing protocols.
  Open for: cli, audit, testing, ux, devex, pack:cli
  Bodies:
  - SKILL: `skills/wxb-pack-cli-devex/skill/SKILL.md`
  - SKILL: `skills/wxb-pack-cli-devex/skill-2/SKILL.md`
  - SKILL: `skills/wxb-pack-cli-devex/skill-3/SKILL.md`
  - SKILL: `skills/wxb-pack-cli-devex/skill-4/SKILL.md`
  - CLI Human Simulator: `skills/wxb-pack-cli-devex/skill-5/SKILL.md`
  - Read-Only CLI Audit: `skills/wxb-pack-cli-devex/skill-6/SKILL.md`
  - CLI Testing & UX/DevEx Audit: `skills/wxb-pack-cli-devex/skill-7/SKILL.md`
  - UX/DevEx Testing Protocol: `skills/wxb-pack-cli-devex/skill-8/SKILL.md`
- Core quality, discipline, handoff, and launch review (`wxb-pack-core-quality`): Evidence-based code review, engineering standards, post-change testing, runbook handoffs, docs index hygiene, SOTA prompting meta, plan-first orchestration, technical assessment for launches, and agent charter / governance audits.
  Open for: quality, standards, handoff, launch, plan-first, governance, charter-audit, pack:core
  Bodies:
  - Prompt: `skills/wxb-pack-core-quality/skill/SKILL.md`
  - Prompt: `skills/wxb-pack-core-quality/skill-2/SKILL.md`
  - Post-Change Testing Instructions: `skills/wxb-pack-core-quality/skill-3/SKILL.md`
  - Complete and Handoff: `skills/wxb-pack-core-quality/skill-4/SKILL.md`
  - Inject AGENTS.md Docs Index: `skills/wxb-pack-core-quality/skill-5/SKILL.md`
  - SOTA Prompting Meta-Skill: `skills/wxb-pack-core-quality/skill-6/SKILL.md`
  - SKILL: `skills/wxb-pack-core-quality/skill-7/SKILL.md`
  - Technical Assessment & Early Adopter Protocol: `skills/wxb-pack-core-quality/skill-8/SKILL.md`
  - Agent charter audit: `skills/wxb-pack-core-quality/skill-9/SKILL.md`
- Long-form prompts (artifact normalization toolkit) (`wxb-pack-longform-prompts`): Copy/paste prompt bodies for repository artifact normalization: primary prompt, meta-evaluator, scoring rubric, and index. Lives at repo-root prompts/; not Codex SKILL.md discovery files.
  Open for: prompts, meta, authoring, normalization, portable-core, pack:prompts
  Bodies:
  - Global prompts (`~/.metactl/prompts`): `skills/wxb-pack-longform-prompts/readme/SKILL.md`
  - Repository artifact normalization (primary prompt): `skills/wxb-pack-longform-prompts/repository-artifact-normalization/SKILL.md`
  - Evaluate a candidate “artifact normalization” prompt: `skills/wxb-pack-longform-prompts/evaluate-artifact-normalization-prompt/SKILL.md`
  - Scoring rubric: repository artifact normalization prompts: `skills/wxb-pack-longform-prompts/artifact-normalization-scoring-rubric/SKILL.md`
- Research, context bundles, and advanced refactor patterns (`wxb-pack-research-context`): Date-aware technical research, evidence-backed UI/UX plus agent-experience (AX) research, GitHub repo+issues bundling for holistic context, and OODA/reflexion-style Python refactor agent patterns.
  Open for: research, context, refactor, repo
  Bodies:
  - Research Technical SOTA for Future-Proof Implementation: `skills/wxb-pack-research-context/skill/SKILL.md`
  - Research UI/UX for Similar Applications: `skills/wxb-pack-research-context/skill-2/SKILL.md`
  - UX + AX Research: `skills/wxb-pack-research-context/skill-3/SKILL.md`
  - Repo bundle with issues: `skills/wxb-pack-research-context/skill-4/SKILL.md`
  - Continual Learning Architecture (OODA Loop Implementation): `skills/wxb-pack-research-context/skill-5/SKILL.md`
- Session memory and reflective improvement (`wxb-pack-session-memory`): Observational memory (observer/reflector) and reflect skill for persisting learnings into skill files.
  Open for: session, memory, reflection, pack:session
  Bodies:
  - From ~/.metactl/skills/observational-memory (or project skills/observational-memory):: `skills/wxb-pack-session-memory/skill/SKILL.md`
  - Reflect: Self-Improving Intelligence Layer: `skills/wxb-pack-session-memory/skill-2/SKILL.md`
<!-- metactl:end agents-md -->
