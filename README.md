# OpenDream

OpenDream is a local-first memory subsystem for coding agents. It captures immutable evidence, derives typed memory candidates, consolidates durable memory with provenance, and exposes reproducible CLI workflows for bootstrap, consolidation, retrieval, and demo runs.

## What’s in this repo
- `opendream_memory/` - runtime package for events, candidates, consolidation, retrieval, and storage
- `tests/` - fixture-driven integration and validation tests
- `specs/401-autodream-style-memory-subsystem/` - canonical implementation spec
- `openspec/changes/401-autodream-style-memory-subsystem/` - proposal bundle and design artifacts
- `docs/` - repo-wide architecture and governance docs

## Quick start
```bash
make setup
make demo
make verify
```

## CLI
Run the memory subsystem directly from the repo root:

```bash
python3 -m opendream_memory.cli init --workspace .tmp/workspace
python3 -m opendream_memory.cli demo --workspace .tmp/demo
python3 -m opendream_memory.cli bootstrap-index --workspace .tmp/workspace --events tests/fixtures/bootstrap_events.jsonl
python3 -m opendream_memory.cli consolidate --workspace .tmp/workspace
python3 -m opendream_memory.cli retrieve --workspace .tmp/workspace --query "package manager and workflow"
```

## Verification
- `make lint`
- `make typecheck`
- `make test`
- `make verify`

## Docs
- [NORTHSTAR.md](/Users/reynard/src/pylit-ai/opendream/NORTHSTAR.md)
- [PRD.md](/Users/reynard/src/pylit-ai/opendream/PRD.md)
- [CONSTITUTION.md](/Users/reynard/src/pylit-ai/opendream/CONSTITUTION.md)
- [AGENTS.md](/Users/reynard/src/pylit-ai/opendream/AGENTS.md)

## Generated data
Memory artifacts are written under a workspace-local `memory/` directory. The demo command creates a deterministic example workspace under `.tmp/demo` by default.
