# spec.md — 420-truthful-verification-and-release

## Title
Make verification and release authoritative for transcript-native dreaming

## Why
`410-truthful-verification` and `413-authoritative-release-gate` established honest gates, but they were centered on the pre-418 surface. Once transcript-native dreaming becomes canonical, the gates must prove that path directly: `make verify` should run dream fidelity, and `make release-check` should install the package cleanly, exercise `dream run`, run `eval dream-fidelity`, and emit manifests every time.

## In scope
- `make verify` including `eval dream-fidelity`
- `make release-check` including clean-venv `dream run` and `eval dream-fidelity`
- deterministic verification and release manifests
- time-bounded release stages
- blocker resolution against the new `418-420` task bundles
- README verification and release language aligned to the actual gates

## Out of scope
- hosted CI vendor selection
- artifact signing and publication automation
- external observability backends

## User-visible behavior
- `make verify` fails if transcript-native dream fidelity fails even when unit tests still pass.
- `make release-check` proves the installed package can run `dream run` and `eval dream-fidelity`, not just `demo`.
- both verify and release-check emit machine-readable manifests on every run.

## Acceptance criteria
- [x] AC-1: `make verify` emits `verification_report.json` and includes a `dream-fidelity-eval` stage
- [x] AC-2: `make release-check` emits `release_manifest.json` and includes `cli-help`, `dream-run`, `eval-dream-fidelity`, and `verify-clean-venv`
- [x] AC-3: release stages remain time-bounded and fail honestly on timeout or lock contention
- [x] AC-4: clean-venv smoke can run `opendream-memory dream run` and `opendream-memory eval dream-fidelity`
- [x] AC-5: release blocker resolution prefers `418-420` once those canonical task files exist
- [x] AC-6: README verification and release language matches the actual scripted gates

## Edge cases
- running the release gate before the new canonical spec tasks exist
- installed-package smoke using packaged fixtures instead of repo-relative test files
- partial pass conditions where old blockers and new blockers would diverge

## Required verifiers
- unit tests: yes, manifest and clean-venv smoke coverage
- integration tests: yes, `make verify` and `make release-check`
- evals / scenario checks: yes, transcript-native fidelity as part of `make verify`
- manual verification: yes, inspect `.tmp/verification/verification_report.json` and `.tmp/release-check/release_manifest.json`

## Risks
- release-check can slow down if too many installed-package smoke commands are added without discipline
- a blocker fallback can hide stale spec lifecycle state if the registry is not kept current

## Links
- `../410-truthful-verification/spec.md`
- `../413-authoritative-release-gate/spec.md`
- `../419-dream-fidelity-evals/spec.md`
- `../../README.md`
