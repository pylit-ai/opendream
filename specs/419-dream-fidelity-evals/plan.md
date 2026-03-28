# plan.md — 419-dream-fidelity-evals

## Summary
Add one explicit fidelity eval for the transcript-native DreamRunner rather than inferring fidelity from the broader unit suite. Keep it deterministic, machine-readable, and runnable from an installed package.

## Architecture impact
- touched components:
  - `opendream_memory.evaluation`
  - `opendream_memory.cli`
  - packaged fixtures under `opendream_memory/fixtures/`
  - `tests/test_memory_cli.py`
  - `tests/test_release_artifact.py`
  - `README.md`
- unchanged components:
  - retrieval scoring logic from `412-memory-quality`
  - release manifest format outside added stages

## Data model / contract changes
- add packaged `dream_fidelity_transcript.jsonl`
- add `eval dream-fidelity` JSON result contract with per-check booleans and embedded run summary

## Interfaces
- input: `opendream eval dream-fidelity --workspace <path>`
- output: deterministic JSON verdict and check map

## Observability
- fidelity eval returns the embedded dream summary, dream status snapshot, and selected retrieval titles
- installed-package smoke now proves the transcript-native eval path, not just `demo`

## Security / safety review
- auth changes: none
- secret handling: packaged eval fixtures are synthetic and non-sensitive
- irreversible actions: none

## Rollout
1. add the packaged transcript fixture
2. implement the eval runner and CLI subcommand
3. add repo and clean-venv smoke coverage
4. update verification and README references

## Rollback
1. remove the dedicated eval command
2. rely on transcript CLI tests and `eval memory-quality` only

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli tests.test_release_artifact -v`
- run: `make verify`
- manual checks:
  - run `opendream eval dream-fidelity --workspace <tmp> --compat-mode autodream`

## ADR needed?
- no
