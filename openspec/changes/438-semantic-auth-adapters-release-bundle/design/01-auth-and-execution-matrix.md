# 01-auth-and-execution-matrix.md

## Goal
Replace the current ambiguous “provider configuration” story with an explicit execution/auth matrix.

## Execution strategies
- `deterministic`
- `direct-provider`
- `codex-account`
- `claude-scheduled-task`
- `cursor-automation`

## Auth sources
- `none`
- `provider-api-key`
- `chatgpt-account`
- `claude-account-task`
- `cursor-account-automation`
- `cursor-api-key` (optional programmatic path; not default)
- `unsupported`

## Recommendation policy
Default preference when `--prefer no-extra-key`:
1. Codex account-backed local execution, if available and trusted
2. Claude scheduled-task adapter, when Claude is configured
3. Cursor automation adapter, when Cursor is configured
4. direct-provider, if explicit provider config exists
5. deterministic-only

Default preference when `--prefer direct-provider`:
1. direct-provider if configured
2. no-extra-key vendor-delegated path
3. deterministic-only

## Why Codex is separate
Codex is special because OpenAI documents both:
- sign in with ChatGPT in the CLI/app/IDE
- and an advanced trusted automation pattern that preserves `auth.json` on a trusted runner

That is sufficiently concrete to justify a first-class adapter.

## Why Claude/Cursor are delegated
Claude scheduled tasks and Cursor automations are strong vendor-owned background runtimes, but OpenDream should treat them as delegated execution unless and until a supported external session-reuse contract exists.
