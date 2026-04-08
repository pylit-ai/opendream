# release-gates.md — 441-workspace-catalog-dashboard-bundle

A release candidate is blocked unless all gates below pass.

## RG-1 Derived-not-canonical
- the workspace catalog is explicitly documented and implemented as derived machine-local state
- per-workspace `.opendream/` metadata remains canonical

## RG-2 Explicit root scans
- no default whole-home scan exists
- configured roots are explicit and inspectable
- scan results are machine-readable and logged

## RG-3 CLI completeness
- `workspace list`, `workspace inspect`, `workspace scan`, `workspace roots add/remove/list`, `workspace forget`, and `workspace doctor` exist and are tested

## RG-4 Dashboard completeness
- UI has a `/workspaces` route
- cards show enough status to be useful:
  - path/name
  - activation state
  - service state
  - memory root
  - semantic mode/health if configured
  - last-seen / missing / stale state
- dashboard links into existing workspace detail views

## RG-5 Docs honesty
- README / FAQ / architecture docs / coding-agent docs explain:
  - current repo-local state
  - new machine-local catalog
  - privacy/safety boundaries
- docs do not imply hidden remote sync or silent disk scanning

## RG-6 Constitution compatibility
- failures in catalog updates are visible
- no silent fallback hides catalog failure
- no destructive mutation of workspace-local state occurs through catalog refresh

## RG-7 Verification
- `make verify` includes catalog/dashboard tests
- scan/report fixtures and dashboard fixtures pass
