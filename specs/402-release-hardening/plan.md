# plan.md — 402-release-hardening

## Summary
Make the repository self-contained by moving runtime schema resolution to package-owned assets, adding packaging metadata and release docs, and validating the install path in automated tests.

## Architecture impact
- touched components:
  - `opendream_memory.util` and `opendream_memory.validation`
  - packaged schema assets under `opendream_memory/schema/`
  - canonical schema copies under `specs/401-autodream-style-memory-subsystem/schema/`
  - release metadata and packaging files at repo root
  - verification tests covering schema presence and installed CLI behavior
- unchanged components:
  - core consolidation and retrieval logic

## Data model / contract changes
- no semantic runtime model changes
- runtime contract assets move from repo-relative proposal lookup to package-local lookup

## Interfaces
- input: `pip install .`, `opendream --help`, `opendream demo --workspace <path>`
- output: installed console entrypoint and deterministic demo artifacts

## Observability
- keep existing runtime audit behavior unchanged
- add install smoke test output and schema drift assertions to verification

## Security / safety review
- auth changes: none
- secret handling: unchanged
- external services: none
- irreversible actions: none

## Rollout
1. add release-hardening spec bundle
2. package schema assets and update runtime lookup
3. add pyproject and release metadata
4. add schema/install smoke tests and rerun `make verify`

## Rollback
1. remove release-hardening files and tests
2. revert runtime schema lookup to repo-local mode if packaging is intentionally abandoned

## Verification plan
- run: `make lint`
- run: `make typecheck`
- run: `make test`
- run: `make verify`
- manual checks:
  - create a clean venv and run `pip install .`
  - run `opendream --help`

## ADR needed?
- no
