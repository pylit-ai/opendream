# 438-semantic-auth-adapters-release-bundle

## Why
OpenDream now exposes semantic sleep-time surfaces and documentation, but the operator story is still ambiguous in the exact place where release credibility is won or lost: **how semantic mode actually runs, how it authenticates, and when users do or do not need extra provider keys**.

Today the repository risks two release failures:

1. **Documentation ambiguity**  
   The docs imply that semantic mode is a generally available provider-backed feature, but the setup path, auth source, and execution boundary are not explicit enough for operators to know whether OpenDream itself is calling a provider, whether a vendor runtime is doing the work, or whether the feature is still partly scaffolded.

2. **Avoidable setup friction**  
   Many likely users already pay for Claude Code, Codex, or Cursor. If OpenDream forces them into separate API-key setup by default, adoption suffers even where a supported account-backed or vendor-delegated path already exists.

This bundle makes the setup unambiguous, stops release notes from implying magic, and makes **“no extra key when possible”** the default semantic execution policy without relying on unsupported token piggybacking.

## Goal
Ship a release-ready semantic execution stack with:
- an explicit execution/auth matrix
- a setup wizard that prefers no-extra-key paths when they are actually supported
- a Codex account-auth semantic adapter
- a Claude scheduled-task semantic adapter
- a Cursor automation semantic adapter
- delegated-ingest contracts for vendor-run semantic refresh
- status/UI/docs/release notes that precisely describe what is supported

## What Changes
- extend semantic configuration from a vague provider switch into an explicit **execution strategy** resolver
- add first-class semantic adapters for:
  - `codex-account`
  - `claude-scheduled-task`
  - `cursor-automation`
- keep direct-provider mode as a supported fallback, not the default recommendation
- add `semantic setup` and `semantic adapters ...` command surfaces
- add delegated semantic envelope/ingest flows so vendor-run background tasks can write results back into OpenDream safely
- update status surfaces, contract export, and web/read-model views so operators can see which execution path is active
- update README / FAQ / playbooks / release notes / benchmark docs so the docs stop promising more than the code actually does
- add policy guardrails so OpenDream does **not** suggest unsupported OAuth reuse patterns (especially Gemini CLI third-party OAuth piggybacking)

## Non-goals
- generic third-party reuse of arbitrary vendor OAuth sessions
- scraping or parsing private token caches outside supported product/runtime boundaries
- public-runner use of Codex account auth
- claiming Claude/Cursor/Codex semantic parity beyond the documented adapter support and tested release gates
- adding a Gemini OAuth-reuse adapter

## Success criteria
- operators can run `opendream semantic setup --prefer no-extra-key` and get a deterministic, explicit recommendation
- the active semantic execution strategy is visible in CLI status, contract export, and observability surfaces
- Codex account-auth execution works on trusted local/private infrastructure without requiring a separate API key
- Claude scheduled-task and Cursor automation flows can run semantic refresh under the user’s existing vendor plan and return results to OpenDream through delegated ingest
- docs and release notes explicitly distinguish:
  - direct-provider mode
  - vendor-delegated mode
  - unsupported paths
  - trust/safety requirements
- release gates fail if docs still imply unsupported magic or hide setup requirements
