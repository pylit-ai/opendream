# ADR-004: Automation engine registry

## Status
Proposed

## Context
`skill_ref` and unattended automation must not become arbitrary shell execution. A declared engine registry is required.

## Decision
TBD — promote when WS6 lands. Built-in engines use `builtin://` identifiers; plugins use versioned `plugin://` ids with side-effect class and approval policy.

## Consequences
Automation registration resolves engines through the registry; unknown engines fail closed.

## Alternatives considered
- Cron + free-form scripts (rejected: unauditable)
- Only built-in engines forever (rejected: blocks extensibility)

## References
- `openspec/changes/agent-ready-platform-complete/design/04-automation-engine-registry.md`
