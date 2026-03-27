# spec.md — 402-release-hardening

## Title
Make the OpenDream repository self-contained and release-safe

## Why
The runtime and tests currently depend on schema assets and repo layout assumptions that are safe in a working tree but brittle in a distributed artifact. The repo also lacks packaging metadata and release-policy files. This change closes those gaps so a fresh checkout or install is self-consistent.

## In scope
- embed runtime schemas inside the package and keep canonical spec copies in `specs/`
- add Python packaging metadata and console entrypoint
- add release metadata files for changelog, security reporting, and licensing
- add automated schema-presence and install smoke tests
- update README and commands to reflect release-safe usage

## Out of scope
- hosted distribution infrastructure
- remote sync, cloud services, or CI automation outside repo-local verifiers
- broad product-direction changes unrelated to release hardening

## User-visible behavior
- A fresh checkout should pass `make verify` without recreating missing schema files.
- `pip install .` should install the package and expose `opendream-memory`.
- The installed CLI should run a deterministic demo without depending on repo-relative schema lookup.

## Acceptance criteria
- [x] AC-1: runtime schema lookup resolves from packaged assets rather than `openspec/...` paths
- [x] AC-2: canonical schema files exist under `specs/401-autodream-style-memory-subsystem/schema/`
- [x] AC-3: `pip install .` succeeds in a clean virtual environment and `opendream-memory --help` works
- [x] AC-4: install smoke test can run `opendream-memory demo --workspace <path>` and produce memory artifacts
- [x] AC-5: release metadata exists for `LICENSE`, `CHANGELOG.md`, and `SECURITY.md`

## Edge cases
- schema copies drifting between package and canonical spec surface
- installed CLI running outside the repo root
- local repo junk files leaking into release verification

## Required verifiers
- unit tests: yes, schema-presence and contract-drift checks
- integration tests: yes, clean-venv install smoke test
- evals / scenario checks: no
- manual verification: yes, `make verify` and `opendream-memory --help` after local install

## Risks
- release metadata can imply a support or licensing posture that is broader than intended
- packaging smoke tests can become slow if they create isolated environments inefficiently

## Links
- `../../specs/401-autodream-style-memory-subsystem/spec.md`
- `../../README.md`
