@AGENTS.md
@docs/governance/DOCS_SYSTEM.md

<!-- metactl:begin claude-md -->
# Repository Builder

Target: Claude Code
Policy: Brownfield Safe Builder

Prefer retrieval-led reasoning: use this file as a compact index, then open the referenced pack body that matches the task.

## Active Pack Index
Mode: reference_index
- Authoring metactl artifacts and prompt systems (`wxb-pack-authoring`): Scaffold commands, skills, rules, workflows; prompt optimization; generalize prompts; generate commands/skills from SOTA docs; preserve skills globally; mine transcripts for automation; steward wx-b metactl-library growth and metactl v2alpha compatibility.
  Open for: meta, authoring, automation, library, maintenance, pack:authoring
  Bodies:
  - Meta-skill: Create a metactl Command: `.claude/packs/wxb-pack-authoring/meta-create-command/SKILL.md`
  - Meta-skill: Create or Maintain metactl Rules: `.claude/packs/wxb-pack-authoring/meta-create-rules/SKILL.md`
  - Meta-skill: Create a metactl Skill: `.claude/packs/wxb-pack-authoring/meta-create-skill/SKILL.md`
  - Meta-skill: Create a metactl Workflow: `.claude/packs/wxb-pack-authoring/meta-create-workflow/SKILL.md`
  - Meta prompt optimization: `.claude/packs/wxb-pack-authoring/meta-prompt-optimization/SKILL.md`
  - Meta prompt optimization (strict): `.claude/packs/wxb-pack-authoring/meta-prompt-optimization-strict/SKILL.md`
  - Generalize Prompt (Meta-Prompting Skill): `.claude/packs/wxb-pack-authoring/generalize-prompt/SKILL.md`
  - Generate Commands and Skills from SOTA Prompting: `.claude/packs/wxb-pack-authoring/generate-commands-skills/SKILL.md`
  - Skill Preserve: `.claude/packs/wxb-pack-authoring/skill-preserve/SKILL.md`
  - Workflow Miner: `.claude/packs/wxb-pack-authoring/workflow-miner/SKILL.md`
  - metactl-library steward: `.claude/packs/wxb-pack-authoring/metactl-library-steward/SKILL.md`
- Charter audit Cursor harness (command + rule) (`wxb-pack-charter-harness`): Slash command and Cursor rule backing /agent-charter-audit; pairs with wxb-pack-core-quality agent-charter-audit SKILL.md. Emitted by metactl compile for targets that project command/rule pack resources.
  Open for: governance, meta, cursor, charter-audit, pack:governance
  No detailed instruction body was emitted for this pack.
- CLI UX, DevEx, and audit harness (`wxb-pack-cli-devex`): Dogfood audits, read-only and exec CLI reviews, human sim harnesses, OpenSpec backlog export, and UX/DevEx testing protocols.
  Open for: cli, audit, testing, ux, devex, pack:cli
  Bodies:
  - SKILL: `.claude/packs/wxb-pack-cli-devex/cli-audit/SKILL.md`
  - SKILL: `.claude/packs/wxb-pack-cli-devex/cli-dogfooding-audit/SKILL.md`
  - SKILL: `.claude/packs/wxb-pack-cli-devex/cli-dogfooding-audit-openspec/SKILL.md`
  - SKILL: `.claude/packs/wxb-pack-cli-devex/cli-dogfooding-audit-readonly/SKILL.md`
  - CLI Human Simulator: `.claude/packs/wxb-pack-cli-devex/cli-human-sim/SKILL.md`
  - Read-Only CLI Audit: `.claude/packs/wxb-pack-cli-devex/cli-readonly-audit/SKILL.md`
  - CLI Testing & UX/DevEx Audit: `.claude/packs/wxb-pack-cli-devex/cli-testing-audit/SKILL.md`
  - UX/DevEx Testing Protocol: `.claude/packs/wxb-pack-cli-devex/ux-devex-testing/SKILL.md`
- Core quality, discipline, handoff, and launch review (`wxb-pack-core-quality`): Evidence-based code review, engineering standards, post-change testing, runbook handoffs, docs index hygiene, SOTA prompting meta, plan-first orchestration, technical assessment for launches, and agent charter / governance audits.
  Open for: quality, standards, handoff, launch, plan-first, governance, charter-audit, pack:core
  Bodies:
  - Prompt: `.claude/packs/wxb-pack-core-quality/code-review/SKILL.md`
  - Prompt: `.claude/packs/wxb-pack-core-quality/engineering-discipline/SKILL.md`
  - Post-Change Testing Instructions: `.claude/packs/wxb-pack-core-quality/post-change-testing/SKILL.md`
  - Complete and Handoff: `.claude/packs/wxb-pack-core-quality/complete-and-handoff/SKILL.md`
  - Inject AGENTS.md Docs Index: `.claude/packs/wxb-pack-core-quality/inject-agents-md-docs-index/SKILL.md`
  - SOTA Prompting Meta-Skill: `.claude/packs/wxb-pack-core-quality/sota-prompting-meta/SKILL.md`
  - SKILL: `.claude/packs/wxb-pack-core-quality/x-claude-workflow-orchestration/SKILL.md`
  - Technical Assessment & Early Adopter Protocol: `.claude/packs/wxb-pack-core-quality/technical-assessment/SKILL.md`
  - Agent charter audit: `.claude/packs/wxb-pack-core-quality/agent-charter-audit/SKILL.md`
- Long-form prompts (artifact normalization toolkit) (`wxb-pack-longform-prompts`): Copy/paste prompt bodies for repository artifact normalization: primary prompt, meta-evaluator, scoring rubric, and index. Lives at repo-root prompts/; not Codex SKILL.md discovery files.
  Open for: prompts, meta, authoring, normalization, portable-core, pack:prompts
  Bodies:
  - Global prompts (`~/.metactl/prompts`): `.claude/packs/wxb-pack-longform-prompts/prompts/README.md`
  - Repository artifact normalization (primary prompt): `.claude/packs/wxb-pack-longform-prompts/prompts/repository-artifact-normalization.md`
  - Evaluate a candidate “artifact normalization” prompt: `.claude/packs/wxb-pack-longform-prompts/prompts/evaluate-artifact-normalization-prompt.md`
  - Scoring rubric: repository artifact normalization prompts: `.claude/packs/wxb-pack-longform-prompts/prompts/artifact-normalization-scoring-rubric.md`
- Research, context bundles, and advanced refactor patterns (`wxb-pack-research-context`): Date-aware technical research, evidence-backed UI/UX plus agent-experience (AX) research, GitHub repo+issues bundling for holistic context, and OODA/reflexion-style Python refactor agent patterns.
  Open for: research, context, refactor, repo
  Bodies:
  - Research Technical SOTA for Future-Proof Implementation: `.claude/packs/wxb-pack-research-context/research-technical-sota/SKILL.md`
  - Research UI/UX for Similar Applications: `.claude/packs/wxb-pack-research-context/research-ui-ux/SKILL.md`
  - UX + AX Research: `.claude/packs/wxb-pack-research-context/ux-ax-research/SKILL.md`
  - Repo bundle with issues: `.claude/packs/wxb-pack-research-context/repo-bundle-with-issues/SKILL.md`
  - Continual Learning Architecture (OODA Loop Implementation): `.claude/packs/wxb-pack-research-context/python-refactorer/SKILL.md`
- Session memory and reflective improvement (`wxb-pack-session-memory`): Observational memory (observer/reflector) and reflect skill for persisting learnings into skill files.
  Open for: session, memory, reflection, pack:session
  Bodies:
  - From ~/.metactl/skills/observational-memory (or project skills/observational-memory):: `.claude/packs/wxb-pack-session-memory/observational-memory/SKILL.md`
  - Reflect: Self-Improving Intelligence Layer: `.claude/packs/wxb-pack-session-memory/reflect/SKILL.md`
<!-- metactl:end claude-md -->
