# plan.md — 410-truthful-verification

## Summary
Replace the placeholder verification surface with a real repository verifier. Standardize tool config in `pyproject.toml`, emit a structured verdict artifact, and make memory writes auditable by default.

## Architecture impact
- touched components:
  - verification scripts and Make targets
  - runtime write-path auditing
  - tests for adversarial probes and report contracts
  - docs that describe verification and release readiness
- unchanged components:
  - external service posture
  - framework adapter boundaries

## Data model / contract changes
- add `verification_report.json`
- add write-audit JSON and diff artifacts for direct memory mutations

## Interfaces
- input: `make verify`, `python3 scripts/verify.py`
- output: machine-readable verdict plus per-stage evidence

## Observability
- verification stage timings and verdicts
- write audit summaries for event and dream/consolidation runs

## Security / safety review
- auth changes: none
- secret handling: existing sensitive-event blocking remains in force
- irreversible actions: none

## Rollout
1. add canonical spec and config surface
2. land real lint and typecheck
3. add verification runner and report
4. update docs and tests

## Rollback
1. remove verification runner and config
2. restore previous Make targets

## Verification plan
- run: `make lint`
- run: `make typecheck`
- run: `make test`
- run: `make verify`
- manual checks:
  - inspect `verification_report.json`
  - inspect write summary and diff artifacts under `memory/audit/`

## ADR needed?
- no
