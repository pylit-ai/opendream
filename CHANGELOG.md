# Changelog

## Unreleased

### Semantic auth adapters release bundle (438)
- **Execution strategy matrix**: semantic mode now classifies runs by execution strategy (`deterministic`, `direct-provider`, `codex-account`, `claude-scheduled-task`, `cursor-automation`) and auth source. Status surfaces, contract export, and observability show the active strategy.
- **Setup wizard**: `opendream semantic setup --workspace . --prefer no-extra-key` detects installed tools and recommends the best no-extra-key execution path. Machine-readable setup report output.
- **Codex account-auth adapter**: Uses Codex CLI as a local subprocess for semantic synthesis on trusted local/private infrastructure. No separate API key required.
- **Claude scheduled-task adapter**: Delegates semantic refresh to Claude as a scheduled task. Results return via validated delegated semantic envelopes.
- **Cursor automation adapter**: Delegates semantic refresh to a Cursor Automation. Results return via validated delegated semantic envelopes.
- **Delegated envelope ingest**: `opendream semantic ingest --workspace . --scan-inbox` validates and ingests delegated envelopes through the standard verify-promote pipeline. Invalid envelopes are archived with failure reasons.
- **Unsupported path guardrails**: Gemini CLI OAuth reuse is explicitly unsupported and never recommended. Public/untrusted CI contexts never default to account-backed mode.
- **New schemas**: `semantic-adapter-manifest`, `semantic-adapter-status`, `semantic-setup-report`, `delegated-semantic-envelope`, `semantic-execution-policy`.
- **ADRs**: ADR-012 (semantic auth/execution matrix), ADR-013 (delegated semantic ingest model).
- **Docs**: README, FAQ, coding-agents, and architecture docs updated with explicit auth/execution matrix. Docs distinguish direct-provider vs vendor-delegated execution.

## 0.2.0 - 2026-03-29

- Activation and service management (compressed zero-touch UX, memory management hooks).
- README and CLI updates for `dream worker`, `dream enqueue`, and integration model.
- CLI UX polish (spec `431-cli-ux-polish`): actionable hints on bare invocation, non-zero exit when `eval` JSON status is `failed`, explicit `no-episodes` results for `dream run` / `dream enqueue`, clearer `dream worker` vs `dream daemon` help; verify uses a clean workspace for dream-fidelity.

## 0.1.0 - 2026-03-26
- initial local-first memory subsystem runtime
- deterministic CLI workflows for bootstrap, consolidation, retrieval, and demo runs
- release-hardening for packaged schemas, console entrypoint, and install smoke verification
