# DOCS_SYSTEM

## Purpose
This file defines how repository documentation is organized, updated, and consumed by humans and agents.

## Design principle
One concept has one canonical home.
All other files may summarize or link to it, but may not become competing sources of truth.

## Canonical homes
- `NORTHSTAR.md`
  - owns enduring product vision, target users, strategic pillars, and non-goals
- `CONSTITUTION.md`
  - owns project-wide invariants, quality gates, safety rules, and engineering governance
- `AGENTS.md`
  - owns the canonical agent entrypoint, read order, commands, approval boundaries, and routing
- `PRD.md`
  - owns the current product / epic scope, user stories, and success metrics
- `specs/<id>/spec.md`
  - owns change-local behavior, acceptance criteria, and edge cases
- `specs/<id>/plan.md`
  - owns the technical approach, rollout, rollback, and verification plan
- `specs/<id>/tasks.md`
  - owns the ordered execution graph for the change
- `specs/registry.yaml`
  - owns spec lifecycle metadata and overlap declarations
- `docs/adr/*.md`
  - own durable architectural decisions after they stabilize
- `docs/mcp/servers.md`
  - owns MCP server inventory, tool contracts, and trust boundaries
- `CURRENT_STATE.md` (brownfield only)
  - owns descriptive legacy reality
- `MIGRATION_GUARDRAILS.md` (brownfield only)
  - owns rules for changing legacy systems safely

## Precedence order
1. Explicit human request in the current task
2. `CONSTITUTION.md`
3. Active spec bundle (`spec.md`, `plan.md`, `tasks.md`)
4. Path-scoped rules / nearest local instructions
5. `PRD.md`
6. `NORTHSTAR.md`
7. Non-canonical summaries

## Single-source rule
- Do not copy acceptance criteria from specs into `AGENTS.md`.
- Do not copy repo-wide rules from `CONSTITUTION.md` into tool adapters.
- Do not place enduring architecture rationale in specs; promote it to an ADR after acceptance.
- Tool-specific adapters must not introduce new policy.

## Canonical spec surface
- Canonical implementation requirements live only in `specs/<id>/{spec.md,plan.md,tasks.md}`.
- Spec lifecycle and dependency state live only in `specs/registry.yaml`.
- Framework adapters must not define requirements, acceptance criteria, or policy.
- Preferred framework adapter path is `.meta/spec-adapters/<framework>/...`.

## Normative language
- Canonical requirement statements SHOULD use BCP 14 terms from RFC 2119 and RFC 8174.
- Interpret `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` with RFC 8174 uppercase semantics.

## Read order by task type

### If changing repository structure, docs, or agent setup
1. `docs/governance/DOCS_SYSTEM.md`
2. `CONSTITUTION.md`
3. `AGENTS.md`

### If changing product direction or tradeoffs
1. `NORTHSTAR.md`
2. `PRD.md`
3. `CONSTITUTION.md`

### If implementing or changing a feature
1. active `specs/<id>/spec.md`
2. active `specs/<id>/plan.md`
3. active `specs/<id>/tasks.md`
4. `CONSTITUTION.md`
5. relevant skills and path-scoped rules

### If touching legacy code and `CURRENT_STATE.md` exists
1. `CURRENT_STATE.md`
2. `MIGRATION_GUARDRAILS.md`
3. active spec bundle
4. `CONSTITUTION.md`

## Update triggers
- Update `NORTHSTAR.md` when mission, target users, strategic pillars, or non-goals change.
- Update `CONSTITUTION.md` when a project-wide invariant, safety rule, or quality gate changes.
- Update `AGENTS.md` when repo layout, commands, routing, or approval boundaries change.
- Update `PRD.md` when current epic or product scope changes.
- Update a spec bundle when behavior, rollout, rollback, or verification changes.

## Spec lifecycle
Statuses:
- proposed
- active
- blocked
- implemented
- superseded
- archived

Rules:
- only `active` specs may drive implementation
- implemented specs are archived after enduring outcomes are folded into ADRs or canonical docs
- no two active specs may touch the same surface without an explicit dependency or conflict declaration in `specs/registry.yaml`

## Anti-clutter rules
- No new root-level doc without a canonical-home justification.
- No path-scoped rule unless that subtree materially diverges from global practice.
- No skill unless the workflow recurs.
- No adapter file may exceed 40 lines unless justified.
- No implemented spec stays active.

## Governance review cadence
- adapter review: every 30 days
- docs system review: every 90 days
- archive review: every 90 days

## Enforcement expectation
This file is normative for documentation organization.
If the repo drifts, reconcile the docs rather than adding another explanatory markdown file.
