# ADR-003: Plugin and package distribution

## Status
Proposed

## Context
The agent-ready platform requires installable thin shims for Codex, Claude Code, Cursor, and GitHub Copilot without duplicating canonical policy.

## Decision
Generated packages will reference canonical docs and carry provenance metadata only.

## Consequences
Package generators and validation CLI become normative; adapters remain non-authoritative.

## Alternatives considered
- Hand-maintained vendor trees (rejected: drift risk)
- Single mega-adapter repo (rejected: conflicts with canonical precedence)

## References
- `docs/architecture/overview.md`
