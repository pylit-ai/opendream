# plan.md — 420-truthful-verification-and-release

## Summary
Re-anchor the repo’s quality gates on the canonical transcript-native runtime. Keep the existing honest verification machinery, but extend it so verify and release prove the dream path directly and block on the new 418-420 canonical task bundles.

## Architecture impact
- touched components:
  - `scripts/verify.py`
  - `scripts/release_check.py`
  - `tests/test_release_artifact.py`
  - `README.md`
  - canonical spec and registry metadata
- unchanged components:
  - mypy and Ruff tool configuration
  - packaging metadata and wheel or sdist build flow

## Data model / contract changes
- add a `dream-fidelity-eval` stage to `verification_report.json`
- add `dream-run` and `eval-dream-fidelity` stages to `release_manifest.json`

## Interfaces
- input: `make verify`, `make release-check`
- output: deterministic verification and release manifests with transcript-native dream stages

## Observability
- verify manifest shows the dream-fidelity stage explicitly
- release manifest shows clean-venv dream and eval stage verdicts explicitly

## Security / safety review
- auth changes: none
- secret handling: unchanged
- irreversible actions: none

## Rollout
1. add dream-fidelity to the verify script
2. extend release-check with installed-package dream smoke and blocker preference
3. update docs and release smoke tests
4. run the full gates

## Rollback
1. remove the added verify and release stages
2. restore the previous blocker set

## Verification plan
- run: `make verify`
- run: `make release-check`
- manual checks:
  - inspect `.tmp/verification/verification_report.json`
  - inspect `.tmp/release-check/release_manifest.json`

## ADR needed?
- no
