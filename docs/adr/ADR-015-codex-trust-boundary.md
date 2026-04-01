# ADR-015: Codex account-backed trust boundary

## Status
Accepted

## Context
Codex CLI uses account-backed auth stored in `~/.codex/auth.json`. OpenDream can shell out to Codex for semantic synthesis without requiring a separate API key, but this path is only safe on trusted local or private infrastructure. Public CI runners, shared containers, and untrusted environments could expose the Codex auth cache to other processes or users.

## Decision
1. **Codex account-backed execution is restricted to trusted local/private infrastructure.**
2. **The setup wizard detects public CI environments** (GITHUB_ACTIONS, GITLAB_CI, CIRCLECI, TRAVIS, BUILDKITE) and refuses to recommend `codex-account` when any are set.
3. **OpenDream never reads, parses, or logs the contents of `~/.codex/auth.json`.** It only checks for existence to determine availability.
4. **The adapter manifest explicitly documents the trust boundary** as `trusted-local-or-private-infrastructure-only`.
5. **Status and setup reports include warnings** when codex-account is the active strategy on a detected public runner.

## Consequences
- No-extra-key semantic mode via Codex is available on developer machines and private CI.
- Public runners fall back to direct-provider or deterministic mode with an explicit warning.
- The trust boundary is documented in adapter manifests, scaffold READMEs, and docs.
