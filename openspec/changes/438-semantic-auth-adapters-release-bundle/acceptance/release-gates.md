# release-gates.md — 438-semantic-auth-adapters-release-bundle

A release candidate is blocked unless all gates below pass.

## RG-1 Docs honesty
- README, FAQ, coding-agent docs, automation playbook, and release notes agree on what semantic mode supports
- docs distinguish direct-provider vs vendor-delegated execution
- docs state when extra provider keys are required and when they are not
- docs do not imply generic OAuth borrowing

## RG-2 Setup unambiguity
- `opendream semantic setup --prefer no-extra-key` exists
- setup output clearly recommends one of:
  - codex-account
  - claude-scheduled-task
  - cursor-automation
  - direct-provider
  - deterministic-only
- setup report explains why other strategies were not chosen

## RG-3 Codex account adapter
- Codex account-auth adapter exists and can be scaffolded
- health/status check distinguishes trusted/private usage from unsupported/public usage
- adapter docs warn about `auth.json` handling and concurrency rules
- a smoke test validates the wrapper/generator without requiring live credentials in CI

## RG-4 Claude scheduled-task adapter
- adapter can scaffold a runnable repo-local command/skill + task template
- docs distinguish `/loop`, Desktop tasks, Cloud tasks, and GitHub Actions tradeoffs
- delegated results can return into OpenDream through validated ingest
- no claim is made that OpenDream directly borrows Claude auth

## RG-5 Cursor automation adapter
- adapter can scaffold automation prompt/instructions and bounded artifact-in-repo return path
- docs distinguish UI/account-backed automation from API-key programmatic usage
- delegated results can return into OpenDream through validated ingest

## RG-6 Unsupported-path guardrails
- setup wizard never recommends Gemini OAuth reuse
- docs explicitly mark unsupported or policy-risky paths as unsupported
- tests cover negative recommendation behavior

## RG-7 Status and contract surfaces
- semantic status includes active strategy, auth source, health, and fallback path
- contract export includes adapter inventory and auth matrix
- observability/UI surfaces expose last semantic owner and last delegated ingest result

## RG-8 Release evidence
- CHANGELOG / release notes explain semantic execution modes precisely
- benchmark/comparison docs do not claim provider-backed local execution where only delegated mode exists
- release-check fails if forbidden wording remains

## RG-9 Verification
- `make verify` and `make release-check` include:
  - adapter schema tests
  - setup wizard tests
  - delegated ingest tests
  - docs honesty checks
  - release wording checks
