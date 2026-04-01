# 03-codex-adapter.md

## Goal
Support a no-extra-key semantic path using Codex account auth where supported.

## Model
OpenDream invokes Codex CLI as a local trusted subprocess runner for semantic synthesis/verification prompts.

## Constraints
- use only on trusted local/private infrastructure
- treat `~/.codex/auth.json` like a secret
- do not suggest this path for public runners or public repos
- do not parse/refresh tokens manually; let Codex manage its own auth cache

## Adapter responsibilities
- detect Codex CLI presence and configured project
- detect likely account-backed auth availability
- generate a wrapper invocation contract
- validate structured output
- record that the semantic owner is `codex-account`

## Non-goal
- no generic OAuth handoff to OpenDream
- no direct use of Codex token bundles by OpenDream HTTP clients

## Recommended execution
- local trusted machine: use account-backed Codex subprocess mode
- trusted private CI: optional advanced auth-cache mode
- public CI/untrusted infra: recommend API-key direct-provider or deterministic-only
