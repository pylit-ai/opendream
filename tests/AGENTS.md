# Tests — agents

## Purpose

Guidance for `tests/` and verification harnesses.

## Conventions

- Add **tests first** when fixing behavior or adding contracts; keep fixtures under `tests/fixtures/` or `opendream/fixtures/` as appropriate.
- Integration tests often spawn `python -m opendream.cli`; follow patterns in `test_memory_cli.py`.
- **Contract / schema** tests should use `opendream.validation.validate_document` with the same schemas shipped in `opendream/schema/`.

## Agent-ready conformance

- Path-scoped guidance and contract export have lightweight checks in `test_agent_ready_guidance.py` and contract export tests.
