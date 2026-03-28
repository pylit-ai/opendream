# plan.md — 431-cli-ux-polish

## Summary
Tighten the CLI's human-facing ergonomics without disturbing the automation-first JSON surface. Keep outputs deterministic, but align exit codes, empty-input behavior, help text, and docs with what operators and CI actually need.

## Architecture impact
- touched components:
  - `opendream.cli`
  - `opendream.dream`
  - `README.md`
  - `scripts/verify.py`
  - `tests/test_memory_cli.py`
- unchanged components:
  - memory storage format
  - retrieval payload structure
  - release-tooling semantics beyond inheriting eval exits

## Rollout
1. add a small custom argparse wrapper for better hints and examples
2. make eval subcommands drive process exit on failed status
3. make dream run and enqueue explicit when no inputs exist
4. update docs and help text

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- run: `./.venv/bin/python -m ruff check opendream tests scripts`
- run: `./.venv/bin/python -m mypy opendream scripts`
- run: `make verify`
- run: `make release-check`
