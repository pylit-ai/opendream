# Change: Truthful verification and adversarial quality gates

## Why
The current verification story is flattering to itself. Syntax survival is being treated like typechecking, lightweight hygiene is being treated like lint, and the release narrative is stronger than the evidence.

## What Changes
- replace placeholder lint and typecheck with real tool-backed gates
- add deterministic verification orchestration and a verdict contract
- add schema/property-style coverage and adversarial probes
- emit inspectable summaries and diffs for memory mutations
- rewrite docs so verification claims match actual execution

## Impact
- Affected specs: `410-truthful-verification`
- Affected code: `scripts/`, `Makefile`, `pyproject.toml`, `opendream_memory/`, `tests/`, `README.md`
