# ADR-012: Semantic auth/execution matrix

## Status
Accepted

## Context
Semantic mode implies a model call, but the operator story for *who makes the call and how it authenticates* was ambiguous. Operators could not tell whether OpenDream called a provider directly, whether a vendor runtime did the work, or whether the feature was scaffolded but incomplete. This ambiguity risked both setup friction (forcing separate API keys when unnecessary) and release-note dishonesty (implying provider-backed local execution when only delegated or deterministic modes existed).

## Decision
Every semantic execution run is classified by exactly one **execution strategy** and one **auth source**:

| Strategy | Execution owner | Auth source | Ingest mode |
|---|---|---|---|
| `deterministic` | opendream-local | none | n/a |
| `direct-provider` | opendream-local | provider-api-key | direct-report |
| `codex-account` | opendream-local | chatgpt-account | direct-report |
| `claude-scheduled-task` | vendor-runtime | claude-account-task | delegated-envelope |
| `cursor-automation` | vendor-runtime | cursor-account-automation | delegated-envelope |

- **Setup wizard** resolves a single recommended strategy via `opendream semantic setup`.
- **Preferred auth mode** is either `no-extra-key` (default) or `direct-provider`.
- **Gemini CLI OAuth reuse** is explicitly `unsupported` and must never be recommended.
- **Public/untrusted runners** must never default to account-backed execution.

Status surfaces, contract export, and observability always show the active strategy and auth source.

## Consequences
- Operators gain an unambiguous, inspectable picture of how semantic work executes.
- No-extra-key paths are preferred when vendor runtimes support them, reducing adoption friction.
- Direct-provider mode remains fully supported for operators who want full control.
- Docs, release notes, and UI must agree on the active execution model.
- Each new vendor adapter must declare trust boundary, execution owner, auth source, and ingest mode.

## Alternatives considered
- **Single generic provider config**: rejected because it hides the execution owner and auth source.
- **Arbitrary OAuth session reuse**: rejected for security and trust-boundary reasons.
- **Vendor-specific API-key-only paths**: rejected because they force extra setup when account-backed paths exist.

## References
- `opendream/schema/semantic-execution-policy.schema.json`
- `opendream/schema/semantic-adapter-manifest.schema.json`
