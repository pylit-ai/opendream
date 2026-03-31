# 436-agent-ready-platform-complete

**OpenSpec change directory:** `openspec/changes/agent-ready-platform-complete/` (CLI requires a leading letter; registry id remains `436-agent-ready-platform-complete`).

## Why
OpenDream now has a credible core runtime, adapter model, activation flow, and first-class automation projections. What it still lacks is the packaging, discoverability, contract stability, and safety envelope expected by modern coding-agent ecosystems. Without those layers, teams must hand-wire integrations, reverse-engineer outputs, and manually maintain guidance surfaces that should instead be installable, testable, and governed.

## Goal
Make OpenDream fully agent-ready across Codex, Claude Code, Cursor, GitHub Copilot, and generic MCP-enabled environments by shipping installable thin shims, stable contracts, declarative extension surfaces, self-improving automations, and isolated execution for any automation that can mutate code.

## What Changes
- add first-class plugin/distribution surfaces for supported agent ecosystems while preserving canonical governance
- add nested/path-scoped guidance surfaces and generated adapter-specific instruction files
- publish stable machine-readable CLI/output contracts and versioned examples
- replace placeholder MCP inventory docs with a complete server/tool/resource trust model
- implement a declarative automation engine registry behind `skill_ref` with schema-validated plugins and built-ins
- add guidance-drift automations that propose updates to `AGENTS.md`, skills, hooks, and docs from repeated friction
- add isolated worktree execution for code-mutating automation jobs, with approval and provenance rules
- add end-to-end release gates, migration docs, and conformance checks for the complete agent-ready platform

## Non-goals
- remote hosted control plane
- multi-tenant SaaS orchestration
- arbitrary shell scheduling without a declared engine contract
- silent product-code mutation from unattended background jobs
- vendor-specific policy forks that compete with canonical repo governance

## Success criteria
- operators can install or generate thin vendor packages without manually copying snippets
- coding agents can discover stable JSON contracts, path-scoped guidance, and trust boundaries without reverse-engineering the repo
- `skill_ref` resolves only through a declared engine registry with explicit schema and safety policy
- guidance-drift automations can identify repeated friction and produce reviewable proposals to improve repo instructions
- code-mutating automation jobs require isolated worktree execution and leave auditable run artifacts
- the complete platform passes new end-to-end release gates and remains constitution-compliant
